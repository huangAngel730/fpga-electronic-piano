#ifndef SCORE_BLE_BRIDGE_H
#define SCORE_BLE_BRIDGE_H
#include <stddef.h>
#include <stdint.h>
#define BR_FRAME_MAX 142
#define BR_QUEUE_MAX 2
#define BR_FRAGMENT_MAX 20
enum br_error { BR_OK, BR_CRC, BR_FORMAT, BR_BUSY, BR_TIMEOUT, BR_OFFLINE };
typedef struct { uint8_t data[BR_FRAME_MAX]; uint16_t used, target; uint32_t last; uint8_t poison; } br_stream;
typedef struct { uint8_t data[BR_FRAME_MAX]; uint16_t length; } br_frame;
typedef struct {
    br_stream gatt, uart;
    br_frame to_uart[BR_QUEUE_MAX], to_ble[BR_QUEUE_MAX];
    uint8_t nu, nb, connected, error;
    uint32_t epoch, errors;
} br_bridge;
uint16_t br_crc(const uint8_t *p, size_t n);
void br_init(br_bridge *b);
void br_connect(br_bridge *b, int connected);
void br_feed(br_bridge *b, int from_gatt, const uint8_t *p, size_t n, uint32_t ms);
void br_tick(br_bridge *b, uint32_t ms);
int br_pop(br_bridge *b, int to_uart, br_frame *f);
#endif
