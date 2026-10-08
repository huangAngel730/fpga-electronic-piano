/* Exact extracted io_task/gap_event/reset_cb run against the frozen core.
 * Platform mocks are deterministic; this is not ESP-IDF or device execution. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include "bridge.h"
#define pdTRUE 1
#define portMAX_DELAY 0xffffffffu
#define pdMS_TO_TICKS(x) (x)
#define UART_NUM_1 1
#define UART_FIFO_OVF 1
#define UART_BUFFER_FULL 2
#define UART_FRAME_ERR 3
#define UART_PARITY_ERR 4
#define ESP_OK 0
#define BLE_HS_ENOMEM 12
#define BLE_HS_CONN_HANDLE_NONE 0xffff
#define BLE_GAP_EVENT_CONNECT 1
#define BLE_GAP_EVENT_DISCONNECT 2
#define BLE_GAP_EVENT_SUBSCRIBE 3
typedef int SemaphoreHandle_t;
typedef int QueueHandle_t;
typedef struct { int type; } uart_event_t;
struct ble_gap_event {
    int type;
    struct { int status; uint16_t conn_handle; } connect;
    struct { uint16_t attr_handle; uint8_t cur_notify; } subscribe;
};
struct os_mbuf { uint8_t data[142]; unsigned length; };
static br_bridge bridge;
static SemaphoreHandle_t mutex=1;
static uint16_t conn=9, tx_handle=10, status_handle=11;
static uint8_t subscribed;
static QueueHandle_t uart_events=1;
static uint32_t reported;
static jmp_buf finished;
static int held, read_returned, hook_done, phase, action, iteration, iterations;
static unsigned checks, scenarios, notify_new, notify_old;
static int pending_mode;
static uint8_t input[26];
static int input_size;
static void advertise(void) {}
static int gap_event(struct ble_gap_event *,void *);
static void reset_cb(int);
static void check(int value,const char *label) {
    checks++;
    if(!value) { fprintf(stderr,"FAIL %s scenario=%u phase=%d action=%d\n",label,scenarios,phase,action); exit(1); }
}
static void change_identity(void) {
    struct ble_gap_event event;
    hook_done=1;
    memset(&event,0,sizeof(event));
    if(action==4) { reset_cb(1); return; }
    if(action==6) { conn++; return; }
    event.type=BLE_GAP_EVENT_DISCONNECT; gap_event(&event,NULL);
    if(action==1) return;
    event.type=BLE_GAP_EVENT_CONNECT;
    event.connect.status=action==5?1:0;
    event.connect.conn_handle=action==3?9:10;
    gap_event(&event,NULL);
    if(pending_mode) subscribed=1;
}
static int xSemaphoreTake(SemaphoreHandle_t m,uint32_t timeout) {
    (void)m; (void)timeout;
    if(phase==2 && read_returned && !hook_done) change_identity();
    check(!held,"UART_MUTEX_NOT_REENTRANT"); held=1; return pdTRUE;
}
static void xSemaphoreGive(SemaphoreHandle_t m) { (void)m; check(held,"UART_MUTEX_RELEASE"); held=0; }
static int64_t esp_timer_get_time(void) { return 1000*(10+iteration*5); }
static int uart_flush_input(int port) { (void)port; return ESP_OK; }
static int uart_read_bytes(int port,uint8_t *bytes,unsigned count,unsigned ticks) {
    int n=input_size;
    (void)port; (void)count; (void)ticks;
    check(!held,"UART_READ_OUTSIDE_MUTEX");
    if(phase==1 && !hook_done) change_identity();
    if(iteration==1) { n=pending_mode?0:26; input[4]=2; { uint16_t crc=br_crc(input+2,22); input[24]=(uint8_t)crc; input[25]=(uint8_t)(crc>>8); } }
    if(n>0) memcpy(bytes,input,(size_t)n);
    read_returned=1; return n;
}
static int xQueueReceive(QueueHandle_t q,uart_event_t *e,unsigned ticks) { (void)q; (void)e; (void)ticks; return 0; }
static int uart_write_bytes(int port,const uint8_t *b,unsigned n) { (void)port; (void)b; return (int)n; }
static int uart_wait_tx_done(int port,unsigned ticks) { (void)port; (void)ticks; return ESP_OK; }
static struct os_mbuf packet;
static struct os_mbuf *ble_hs_mbuf_from_flat(const void *bytes,unsigned n) { memcpy(packet.data,bytes,n); packet.length=n; return &packet; }
static int ble_gatts_notify_custom(uint16_t c,uint16_t handle,struct os_mbuf *p) {
    (void)c; (void)p;
    if(handle==tx_handle && bridge.epoch!=1) notify_new++;
    if(handle==tx_handle && bridge.epoch==1) notify_old++;
    return BLE_HS_ENOMEM;
}
static void vTaskDelay(unsigned ticks) {
    (void)ticks; check(!held,"UART_END_UNLOCKED"); iteration++; read_returned=0;
    if(pending_mode && iteration==1) { phase=1; action=2; hook_done=0; }
    if(iteration>=iterations) longjmp(finished,1);
}

/* SOURCE_FUNCTIONS: injected verbatim from approved current or old main.c. */

static void scenario(int p,int a,int size,int connected,uint32_t initial_epoch,int recovery) {
    br_frame result;
    uint16_t crc;
    int accepted, stale;
    scenarios++; phase=p; action=a; input_size=size; iterations=recovery?2:1;
    pending_mode=recovery==2;
    held=read_returned=hook_done=iteration=0; subscribed=pending_mode?1:0; reported=0; conn=9; notify_new=notify_old=0;
    br_init(&bridge); br_connect(&bridge,connected); bridge.epoch=initial_epoch;
    memset(input,0,sizeof(input)); input[0]=0xa5; input[1]=0x5a; input[2]=1; input[3]=0x80;
    input[4]=1; input[10]=12; input[12]=4;
    crc=br_crc(input+2,22); input[24]=(uint8_t)crc; input[25]=(uint8_t)(crc>>8);
    if(setjmp(finished)==0) io_task(NULL);
    stale=(p!=0 || !connected);
    accepted=br_pop(&bridge,0,&result);
    if(pending_mode) {
        check(!accepted,"UART_PENDING_QUEUE_CLEARED");
        check(notify_old==1 && notify_new==0,"UART_PENDING_POSITION_EPOCH_CLEARED");
    } else if(recovery) {
        check(accepted && result.data[4]==2,"UART_RECOVERY_CURRENT_ACK");
        check(!br_pop(&bridge,0,&result),"UART_NO_STALE_EXTRA_ACK");
    } else if(size==26 && !stale) check(accepted && result.data[4]==1,"UART_CURRENT_ACK");
    else check(!accepted,"UART_GENERATION_STALE_QUEUE");
    if(stale && !recovery) check(bridge.uart.used==0,"UART_GENERATION_STALE_PARTIAL");
    if(!stale && size==10) check(bridge.uart.used==10,"UART_CURRENT_PARTIAL");
}
int main(void) {
    unsigned i;
    scenario(0,0,26,1,1,0); scenario(0,0,10,1,1,0); scenario(0,0,0,1,1,0);
    scenario(0,0,-1,1,1,0); scenario(0,0,26,0,1,0);
    scenario(1,2,26,0,1,0); scenario(2,3,26,0,1,0);
    for(i=1;i<=6;i++) {
        scenario(1,(int)i,26,1,1,0); scenario(2,(int)i,26,1,1,0);
        scenario(2,(int)i,10,1,1,0);
    }
    scenario(1,2,26,1,1,1); scenario(2,3,26,1,1,1);
    scenario(0,0,26,1,1,2);
    for(i=0;i<128;i++) {
        scenario(1,3,26,1,UINT32_MAX-i,0);
        scenario(2,3,26,1,UINT32_MAX-i,0);
    }
    printf("PASS UART scenarios=%u checks=%u exact_source_functions mock_platform\n",scenarios,checks);
    return 0;
}
