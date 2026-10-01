#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

typedef int (__cdecl *gowin_entry_t)(int, char **, int);
typedef int (__cdecl *gowin_execute_t)(void);

int main(int argc, char **argv) {
    const char *ide_dir =
        "D:\\program\\gaoyunFPGA\\Gowin\\Gowin_V1.9.11.03_Education_x64\\IDE\\bin";
    const char *ide_exe =
        "D:\\program\\gaoyunFPGA\\Gowin\\Gowin_V1.9.11.03_Education_x64\\IDE\\bin\\gw_ide.exe";
    const char *dll_path =
        "D:\\program\\gaoyunFPGA\\Gowin\\Gowin_V1.9.11.03_Education_x64\\IDE\\bin\\gowin.dll";
    const char *symbol = "?readInUserCommand@@YAHHPEAPEAD_N@Z";
    const char *execute_symbol = "?executePnrTask@@YAHXZ";
    char **vendor_argv;
    HMODULE module;
    FARPROC raw;
    gowin_entry_t entry;
    gowin_execute_t execute;
    int index;
    int result;

    if (!SetDllDirectoryA(ide_dir)) {
        fprintf(stderr, "SetDllDirectory failed: %lu\n", GetLastError());
        return 10;
    }
    module = LoadLibraryA(dll_path);
    if (module == NULL) {
        fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError());
        return 11;
    }
    raw = GetProcAddress(module, symbol);
    if (raw == NULL) {
        fprintf(stderr, "GetProcAddress failed: %lu\n", GetLastError());
        FreeLibrary(module);
        return 12;
    }
    entry = (gowin_entry_t)raw;
    raw = GetProcAddress(module, execute_symbol);
    if (raw == NULL) {
        fprintf(stderr, "GetProcAddress execute failed: %lu\n", GetLastError());
        FreeLibrary(module);
        return 14;
    }
    execute = (gowin_execute_t)raw;
    vendor_argv = (char **)calloc((size_t)argc, sizeof(char *));
    if (vendor_argv == NULL) {
        FreeLibrary(module);
        return 13;
    }
    vendor_argv[0] = (char *)ide_exe;
    for (index = 1; index < argc; ++index) {
        vendor_argv[index] = argv[index];
    }
    result = entry(argc, vendor_argv, 1);
    if (result == 0)
        result = execute();
    free(vendor_argv);
    FreeLibrary(module);
    return result;
}
