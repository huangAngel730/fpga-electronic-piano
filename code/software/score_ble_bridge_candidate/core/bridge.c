#include "bridge.h"
#include <string.h>
uint16_t br_crc(const uint8_t *p, size_t n) {
    uint16_t c=0xffff; size_t i; unsigned j;
    for(i=0;i<n;i++) { c^=(uint16_t)p[i]<<8; for(j=0;j<8;j++) c=(uint16_t)((c<<1)^((c&0x8000)?0x1021:0)); }
    return c;
}
static void error(br_bridge *b, uint8_t e) { b->error=e; b->errors++; }
void br_init(br_bridge *b) { memset(b,0,sizeof(*b)); }
void br_connect(br_bridge *b, int connected) {
    uint32_t epoch=b->epoch+1, errors=b->errors;
    br_init(b); b->epoch=epoch; b->errors=errors; b->connected=(uint8_t)(connected!=0);
}
static void timeout(br_bridge *b, br_stream *s, uint32_t ms, uint32_t limit) {
    if ((s->used || s->poison) && (uint32_t)(ms-s->last)>=limit) {
        memset(s,0,sizeof(*s)); error(b,BR_TIMEOUT);
    }
}
void br_tick(br_bridge *b, uint32_t ms) { timeout(b,&b->gatt,ms,2000); timeout(b,&b->uart,ms,20); }
void br_feed(br_bridge *b, int from_gatt, const uint8_t *p, size_t n, uint32_t ms) {
    br_stream *s=from_gatt?&b->gatt:&b->uart; size_t i;
    br_tick(b,ms);
    if(!b->connected) { error(b,BR_OFFLINE); return; }
    for(i=0;i<n;i++) {
        uint8_t v=p[i]; s->last=ms;
        /* After malformed length/CRC/direction ignore until quiet or reconnect;
           never parse embedded magic inside an invalid frame. */
        if(s->poison) continue;
        if(s->used==0) { if(v==0xa5) s->data[s->used++]=v; continue; }
        if(s->used==1 && v!=0x5a) { s->used=(v==0xa5); continue; }
        s->data[s->used++]=v;
        if(s->used==12) {
            uint16_t len=(uint16_t)(s->data[10]|s->data[11]<<8);
            if(len>128 || s->data[2]!=1) { s->poison=1; error(b,BR_FORMAT); continue; }
            s->target=(uint16_t)(14+len);
        }
        if(s->target && s->used==s->target) {
            uint16_t got=(uint16_t)(s->data[s->used-2]|s->data[s->used-1]<<8);
            uint8_t cmd=s->data[3];
            int direction=from_gatt?(cmd>=1 && cmd<=6):(cmd==0x80 || cmd==0x81);
            if(got!=br_crc(s->data+2,s->used-4)) {
                s->poison=1; error(b,BR_CRC); continue;
            }
            if(!direction) { s->poison=1; error(b,BR_FORMAT); continue; }
            {
                uint8_t *count=from_gatt?&b->nu:&b->nb;
                br_frame *queue=from_gatt?b->to_uart:b->to_ble;
                if(*count==BR_QUEUE_MAX) error(b,BR_BUSY);
                else { queue[*count].length=s->used; memcpy(queue[*count].data,s->data,s->used); (*count)++; }
            }
            memset(s,0,sizeof(*s));
        }
    }
}
int br_pop(br_bridge *b, int to_uart, br_frame *f) {
    uint8_t *count=to_uart?&b->nu:&b->nb;
    br_frame *queue=to_uart?b->to_uart:b->to_ble;
    if(!*count || !b->connected) return 0;
    *f=queue[0]; (*count)--; memmove(queue,queue+1,*count*sizeof(*queue)); return 1;
}
