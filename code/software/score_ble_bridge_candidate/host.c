/* Real desktop executable, no UART/device access. Line protocol is test-only. */
#include "core/bridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void print_frame(const char *tag,const br_frame *f) {
    unsigned i; printf("%s ",tag); for(i=0;i<f->length;i++) printf("%02x",f->data[i]); puts("");
}
int main(void) {
    br_bridge b; char line[4096]; br_init(&b);
    while(fgets(line,sizeof(line),stdin)) {
        uint8_t data[1500]; size_t n=0; unsigned ms=0; char hex[3001],cmd=0;
        if(sscanf(line,"%c %u %3000s",&cmd,&ms,hex)<1) return 2;
        if(cmd=='C') br_connect(&b,1);
        else if(cmd=='D') br_connect(&b,0);
        else if(cmd=='T') br_tick(&b,ms);
        else if(cmd=='G'||cmd=='U') {
            size_t i, len=strlen(hex); if(len%2) return 2;
            for(i=0;i<len;i+=2) { char pair[3]={hex[i],hex[i+1],0}; char *end; long v=strtol(pair,&end,16); if(*end) return 2; data[n++]=(uint8_t)v; }
            br_feed(&b,cmd=='G',data,n,ms);
        } else if(cmd=='P') {
            br_frame f; while(br_pop(&b,1,&f)) print_frame("UART",&f);
            while(br_pop(&b,0,&f)) {
                unsigned i; for(i=0;i<f.length;i+=20) { br_frame part; part.length=(uint16_t)((f.length-i>20)?20:f.length-i); memcpy(part.data,f.data+i,part.length); print_frame("NOTIFY",&part); }
            }
        } else if(cmd=='Q') { puts("END"); fflush(stdout); break; }
        else return 2;
        if(b.error) { printf("LOCAL %u\n",b.error); b.error=0; }
        puts("END"); fflush(stdout);
    }
    return 0;
}
