/* Isolated C3 candidate. GPIO4 TX / GPIO5 RX are C3-side choices only.
   No FPGA wiring/programming permission is implied by this source. */
#include <string.h>
#include <stdio.h>
#include "bridge.h"
#include "nvs_flash.h"
#include "esp_timer.h"
#include "esp_mac.h"
#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
/* 761e0001/2/3/4-6ccd-4aa4-9e21-104647415031; LE byte order. */
#define UUID(n) BLE_UUID128_INIT(0x31,0x50,0x41,0x47,0x46,0x10,0x21,0x9e,0xa4,0x4a,0xcd,0x6c,n,0,0x1e,0x76)
static const ble_uuid128_t service=UUID(1), rx=UUID(2), tx=UUID(3), status=UUID(4);
static br_bridge bridge;
static SemaphoreHandle_t mutex;
static uint16_t conn=BLE_HS_CONN_HANDLE_NONE, tx_handle, status_handle;
static uint8_t addr_type, subscribed;
static QueueHandle_t uart_events;
static uint32_t reported;
static uint32_t ms(void) { return (uint32_t)(esp_timer_get_time()/1000); }
static int gap_event(struct ble_gap_event *event,void *arg);
static void advertise(void) {
    struct ble_hs_adv_fields f={0}; struct ble_gap_adv_params p={0};
    f.flags=BLE_HS_ADV_F_DISC_GEN|BLE_HS_ADV_F_BREDR_UNSUP;
    f.uuids128=(ble_uuid128_t *)&service; f.num_uuids128=1; f.uuids128_is_complete=1;
    if(ble_gap_adv_set_fields(&f)) return;
    struct ble_hs_adv_fields scan={0}; const char *name=ble_svc_gap_device_name();
    scan.name=(uint8_t *)name; scan.name_len=strlen(name); scan.name_is_complete=1;
    if(ble_gap_adv_rsp_set_fields(&scan)) return;
    p.conn_mode=BLE_GAP_CONN_MODE_UND; p.disc_mode=BLE_GAP_DISC_MODE_GEN;
    ble_gap_adv_start(addr_type,NULL,BLE_HS_FOREVER,&p,gap_event,NULL);
}
static int access_cb(uint16_t c,uint16_t a,struct ble_gatt_access_ctxt *ctxt,void *arg) {
    (void)a; (void)arg;
    if(xSemaphoreTake(mutex,0)!=pdTRUE) return BLE_ATT_ERR_INSUFFICIENT_RES;
    int rc=0;
    if(c!=conn || !bridge.connected) rc=BLE_ATT_ERR_UNLIKELY;
    else if(ctxt->op==BLE_GATT_ACCESS_OP_WRITE_CHR && ble_uuid_cmp(ctxt->chr->uuid,&rx.u)==0) {
        uint16_t length=OS_MBUF_PKTLEN(ctxt->om); uint8_t bytes[20];
        if(length==0 || length>20 || !subscribed) rc=BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
        else if(os_mbuf_copydata(ctxt->om,0,length,bytes)) rc=BLE_ATT_ERR_UNLIKELY;
        else {
            uint32_t before=bridge.errors; br_feed(&bridge,1,bytes,length,ms());
            if(bridge.errors!=before) rc=BLE_ATT_ERR_UNLIKELY;
        }
    } else if(ctxt->op==BLE_GATT_ACCESS_OP_READ_CHR && ble_uuid_cmp(ctxt->chr->uuid,&status.u)==0) {
        uint8_t local[6]={1,bridge.error,(uint8_t)bridge.epoch,(uint8_t)(bridge.epoch>>8),bridge.nu,bridge.nb};
        rc=os_mbuf_append(ctxt->om,local,sizeof(local))?BLE_ATT_ERR_INSUFFICIENT_RES:0;
    } else rc=BLE_ATT_ERR_READ_NOT_PERMITTED;
    xSemaphoreGive(mutex); return rc;
}
static const struct ble_gatt_svc_def services[]={
    {.type=BLE_GATT_SVC_TYPE_PRIMARY,.uuid=&service.u,.characteristics=(struct ble_gatt_chr_def[]){
        {.uuid=&rx.u,.access_cb=access_cb,.flags=BLE_GATT_CHR_F_WRITE},
        {.uuid=&tx.u,.access_cb=access_cb,.flags=BLE_GATT_CHR_F_NOTIFY,.val_handle=&tx_handle},
        {.uuid=&status.u,.access_cb=access_cb,.flags=BLE_GATT_CHR_F_READ|BLE_GATT_CHR_F_NOTIFY,.val_handle=&status_handle},
        {0}}},{0}};
static int gap_event(struct ble_gap_event *e,void *arg) {
    (void)arg; xSemaphoreTake(mutex,portMAX_DELAY);
    if(e->type==BLE_GAP_EVENT_CONNECT && e->connect.status==0) {
        conn=e->connect.conn_handle; subscribed=0; br_connect(&bridge,1); uart_flush_input(UART_NUM_1);
    } else if(e->type==BLE_GAP_EVENT_DISCONNECT) {
        conn=BLE_HS_CONN_HANDLE_NONE; subscribed=0; br_connect(&bridge,0); uart_flush_input(UART_NUM_1);
    } else if(e->type==BLE_GAP_EVENT_SUBSCRIBE && e->subscribe.attr_handle==tx_handle) subscribed=e->subscribe.cur_notify;
    xSemaphoreGive(mutex);
    if(e->type==BLE_GAP_EVENT_DISCONNECT || (e->type==BLE_GAP_EVENT_CONNECT && e->connect.status)) advertise();
    return 0;
}
static void sync_cb(void) { if(!ble_hs_util_ensure_addr(0) && !ble_hs_id_infer_auto(0,&addr_type)) advertise(); }
static void reset_cb(int reason) { (void)reason; xSemaphoreTake(mutex,portMAX_DELAY); br_connect(&bridge,0); conn=BLE_HS_CONN_HANDLE_NONE; subscribed=0; xSemaphoreGive(mutex); }
static void host_task(void *arg) { (void)arg; nimble_port_run(); nimble_port_freertos_deinit(); }
static void io_task(void *arg) {
    (void)arg; br_frame outgoing; unsigned position=0; uint32_t epoch=0, deadline=0; int pending=0;
    for(;;) {
        uint8_t bytes[256]; int n=uart_read_bytes(UART_NUM_1,bytes,sizeof(bytes),pdMS_TO_TICKS(5));
        xSemaphoreTake(mutex,portMAX_DELAY); uint32_t now=ms(); br_tick(&bridge,now);
        uart_event_t event;
        while(xQueueReceive(uart_events,&event,0)==pdTRUE) {
            if(event.type==UART_FIFO_OVF || event.type==UART_BUFFER_FULL || event.type==UART_FRAME_ERR || event.type==UART_PARITY_ERR) {
                uart_flush_input(UART_NUM_1); memset(&bridge.uart,0,sizeof(bridge.uart));
                bridge.nb=0; pending=0; n=0; bridge.error=BR_FORMAT; bridge.errors++;
            }
        }
        if(epoch!=bridge.epoch || !bridge.connected) { pending=0; position=0; epoch=bridge.epoch; }
        if(n>0 && bridge.connected) br_feed(&bridge,0,bytes,(size_t)n,now);
        br_frame f;
        if(br_pop(&bridge,1,&f)) {
            /* One complete frame / one UART write; no BLE gaps enter its bytes. */
            int written=uart_write_bytes(UART_NUM_1,f.data,f.length);
            if(written!=f.length || uart_wait_tx_done(UART_NUM_1,pdMS_TO_TICKS(30))!=ESP_OK) { bridge.error=BR_TIMEOUT; bridge.errors++; }
        }
        if(subscribed && !pending && br_pop(&bridge,0,&outgoing)) { pending=1; position=0; deadline=now+500; }
        if(pending && subscribed) {
            unsigned length=outgoing.length-position; if(length>20) length=20;
            struct os_mbuf *packet=ble_hs_mbuf_from_flat(outgoing.data+position,length);
            int rc=packet?ble_gatts_notify_custom(conn,tx_handle,packet):BLE_HS_ENOMEM;
            if(!rc) { position+=length; if(position==outgoing.length) pending=0; }
            else if((int32_t)(now-deadline)>=0) { pending=0; bridge.error=BR_TIMEOUT; bridge.errors++; }
        }
        if(bridge.errors!=reported && bridge.connected) {
            uint8_t local[6]={1,bridge.error,(uint8_t)bridge.epoch,(uint8_t)(bridge.epoch>>8),bridge.nu,bridge.nb};
            struct os_mbuf *packet=ble_hs_mbuf_from_flat(local,6);
            if(packet && ble_gatts_notify_custom(conn,status_handle,packet)==0) reported=bridge.errors;
        }
        xSemaphoreGive(mutex); vTaskDelay(pdMS_TO_TICKS(5));
    }
}
void app_main(void) {
    ESP_ERROR_CHECK(nvs_flash_init()); /* No automatic NVS erase. */
    mutex=xSemaphoreCreateMutex(); configASSERT(mutex); br_init(&bridge);
    const uart_config_t cfg={.baud_rate=115200,.data_bits=UART_DATA_8_BITS,.parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,.flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1,&cfg));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1,4,5,UART_PIN_NO_CHANGE,UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1,1024,0,8,&uart_events,0));
    ESP_ERROR_CHECK(nimble_port_init()); ble_svc_gap_init(); ble_svc_gatt_init();
    char name[24]; uint8_t mac[6];
    ESP_ERROR_CHECK(esp_read_mac(mac,ESP_MAC_BT));
    snprintf(name,sizeof(name),"M3-Score-%02X%02X%02X",mac[3],mac[4],mac[5]);
    ble_svc_gap_device_name_set(name); ble_hs_cfg.sync_cb=sync_cb; ble_hs_cfg.reset_cb=reset_cb;
    configASSERT(ble_gatts_count_cfg(services)==0); configASSERT(ble_gatts_add_svcs(services)==0);
    configASSERT(xTaskCreate(io_task,"score_uart",4096,NULL,5,NULL)==pdPASS);
    nimble_port_freertos_init(host_task);
}
