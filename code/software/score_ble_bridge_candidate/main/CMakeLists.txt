idf_component_register(SRCS "main.c" "../core/bridge.c" INCLUDE_DIRS "../core" REQUIRES bt nvs_flash esp_driver_uart esp_timer)
