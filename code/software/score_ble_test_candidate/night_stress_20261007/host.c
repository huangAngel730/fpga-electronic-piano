/* New test-only desktop wrapper. Calls only the frozen public bridge API. */
#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef MUTATION
#define MUTATION 0
#endif

static void dump(const char *tag, const br_frame *frame) {
    unsigned i;
    printf("%s ", tag);
    for (i = 0; i < frame->length; ++i) printf("%02x", frame->data[i]);
    puts("");
}

int main(void) {
    br_bridge bridge;
    char line[8192];
    br_init(&bridge);
    while (fgets(line, sizeof(line), stdin)) {
        unsigned ms = 0;
        uint32_t errors = bridge.errors;
        char command = line[0], hex[6001];
        if (command == 'C' || command == 'D') br_connect(&bridge, command == 'C');
        else if (command == 'T') {
            if (sscanf(line + 2, "%u", &ms) != 1) return 2;
            br_tick(&bridge, ms);
        } else if (command == 'G' || command == 'U') {
            unsigned char data[3000];
            size_t i, n;
            if (sscanf(line + 2, "%u %6000s", &ms, hex) != 2) return 2;
            n = strlen(hex);
            if (n % 2) return 2;
            for (i = 0; i < n; i += 2) {
                char pair[3] = {hex[i], hex[i + 1], 0}, *end;
                data[i / 2] = (unsigned char)strtoul(pair, &end, 16);
                if (*end) return 2;
            }
            br_feed(&bridge, command == 'G', data, n / 2, ms);
        } else if (command == 'P') {
            br_frame frame;
            while (br_pop(&bridge, 1, &frame)) {
                if (MUTATION == 1 && frame.length > 14) frame.data[12] ^= 1;
                dump("UART", &frame);
            }
            while (br_pop(&bridge, 0, &frame)) {
                if (MUTATION == 2) continue; /* compileable missing peer Notify */
                dump("REPLY", &frame);
            }
        } else if (command == 'S') {
            printf("STAT %u %u %u %lu %lu %u\n", bridge.connected, bridge.nu,
                   bridge.nb, (unsigned long)bridge.epoch,
                   (unsigned long)bridge.errors, bridge.error);
        } else if (command == 'Q') {
            puts("END"); fflush(stdout); return 0;
        } else return 2;
        if (bridge.errors != errors) printf("LOCAL %u\n", bridge.error);
        puts("END"); fflush(stdout);
    }
    return 0;
}
