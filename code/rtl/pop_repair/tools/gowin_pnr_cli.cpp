#include <windows.h>

#include <cstdio>
#include <vector>

int main(int argc, char **argv) {
    const char *ide_dir =
        "D:\\program\\gaoyunFPGA\\Gowin\\Gowin_V1.9.11.03_Education_x64\\IDE\\bin";
    const char *ide_exe =
        "D:\\program\\gaoyunFPGA\\Gowin\\Gowin_V1.9.11.03_Education_x64\\IDE\\bin\\gw_ide.exe";
    const char *dll_path =
        "D:\\program\\gaoyunFPGA\\Gowin\\Gowin_V1.9.11.03_Education_x64\\IDE\\bin\\gowin.dll";

    if (!SetDllDirectoryA(ide_dir)) {
        std::fprintf(stderr, "SetDllDirectory failed: %lu\n", GetLastError());
        return 10;
    }
    HMODULE module = LoadLibraryA(dll_path);
    if (module == nullptr) {
        std::fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError());
        return 11;
    }

    const char *symbol = "?readInUserCommand@@YAHHPEAPEAD_N@Z";
    FARPROC raw = GetProcAddress(module, symbol);
    if (raw == nullptr) {
        std::fprintf(stderr, "GetProcAddress failed: %lu\n", GetLastError());
        FreeLibrary(module);
        return 12;
    }

    using Entry = int(__cdecl *)(int, char **, bool);
    Entry entry = reinterpret_cast<Entry>(raw);
    std::vector<char *> vendor_argv;
    vendor_argv.reserve(static_cast<size_t>(argc));
    vendor_argv.push_back(const_cast<char *>(ide_exe));
    for (int index = 1; index < argc; ++index) {
        vendor_argv.push_back(argv[index]);
    }

    const int result = entry(static_cast<int>(vendor_argv.size()),
                             vendor_argv.data(), true);
    FreeLibrary(module);
    return result;
}
