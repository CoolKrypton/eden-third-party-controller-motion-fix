/*
 * hid_dump.c - dump raw HID input reports from a USB gamepad.
 *
 * Used to work out which bits a third party "Switch" controller actually sets
 * for ZL/ZR, since those are the buttons SDL3 turns into trigger axes.
 *
 *   gcc -O2 -o hid_dump.exe tools/hid_dump.c -lsetupapi -lhid
 *   ./hid_dump.exe            # lists every HID device, then dumps 057E:*
 *   ./hid_dump.exe 057E 2009  # dump a specific VID/PID
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <setupapi.h>
#include <hidsdi.h>

#define MAX_PATH_BUF 512

static int g_vid = 0, g_pid = 0; /* 0 = any */

static void hexdump(const unsigned char *buf, int len) {
    for (int i = 0; i < len; ++i) {
        printf("%02X ", buf[i]);
    }
}

static void dump_device(const char *path) {
    HANDLE h = CreateFileA(path, GENERIC_READ,
                           FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                           OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        printf("  CreateFile failed (%lu). Is another program holding the device?\n",
               GetLastError());
        return;
    }

    HIDP_CAPS caps;
    PHIDP_PREPARSED_DATA pp = NULL;
    if (!HidD_GetPreparsedData(h, &pp)) {
        printf("  HidD_GetPreparsedData failed\n");
        CloseHandle(h);
        return;
    }
    HidP_GetCaps(pp, &caps);
    printf("  input report length = %u\n", caps.InputReportByteLength);
    HidD_FreePreparsedData(pp);

    unsigned char buf[256];
    unsigned char prev[256];
    memset(prev, 0, sizeof(prev));
    DWORD read = 0;
    int printed = 0;
    unsigned int or0 = 0, or1 = 0, or2 = 0;
    int samples = 0;
    unsigned char base[256];
    unsigned char diffmask[24];
    int base_len = 0, have_base = 0;
    unsigned char prev_vendor[256];
    int vprinted = 0;
    memset(prev_vendor, 0, sizeof(prev_vendor));
    memset(base, 0, sizeof(base));
    memset(diffmask, 0, sizeof(diffmask));

    FILE *out = fopen("hid_dump.txt", "w");
    if (out) {
        fprintf(out, "HID report dump\n");
    }
    printf("  采样 45 秒：请依次按几下 L、R、ZL、ZR（每键按 2-3 下）\n\n");
    DWORD t0 = GetTickCount();
    while (GetTickCount() - t0 < 45000) {
        if (!ReadFile(h, buf, (DWORD)caps.InputReportByteLength, &read, NULL)) {
            printf("  ReadFile failed (%lu)\n", GetLastError());
            break;
        }
        if (read < 4) {
            continue;
        }
        ++samples;
        or0 |= buf[1];
        or1 |= buf[2];
        or2 |= buf[3];
        /* SDL3 layout: [0]=id [1]=counter [2]=batt/conn [3..5]=buttons
           [6..8]=left stick [9..11]=right stick [12]=vibration */

        /* Record which bytes ever differ from the very first report, so a
           button that lives in an unexpected byte still shows up. */
        if (!have_base) {
            memcpy(base, buf, read);
            base_len = (int)read;
            have_base = 1;
        } else {
            int n = (int)read < base_len ? (int)read : base_len;
            for (int i = 1; i < n && i < 24; ++i) {
                diffmask[i] |= (unsigned char)(buf[i] ^ base[i]);
            }
        }

        /* Vendor reports (0x81 / 0x21) may carry the linear trigger values, so
           print them whenever their payload changes too. */
        int vendor = (buf[0] != 0x30);
        if (vendor) {
            if (memcmp(buf + 1, prev_vendor, (int)read - 1 < 16 ? (int)read - 1 : 16) != 0 &&
                vprinted < 40) {
                printf("  V[%2d] id=%02X  ", vprinted, buf[0]);
                hexdump(buf + 1, (int)read - 1 < 20 ? (int)read - 1 : 20);
                printf("\n");
                fflush(stdout);
                ++vprinted;
            }
            memcpy(prev_vendor, buf + 1, (int)read - 1 < 16 ? (int)read - 1 : 16);
        }

        if (printed < 4 ||
            (memcmp(buf + 3, prev + 3, 3) != 0 && printed < 200)) {
            printf("  [%3d] len=%lu id=%02X  ", printed, (unsigned long)read, buf[0]);
            hexdump(buf + 1, (int)read - 1 < 20 ? (int)read - 1 : 20);
            printf("   btn=[%02X %02X %02X]", buf[3], buf[4], buf[5]);
            printf("  SDL3:R=%d ZR=%d L=%d ZL=%d\n",
                   (buf[3] & 0x40) ? 1 : 0, (buf[3] & 0x80) ? 1 : 0,
                   (buf[5] & 0x40) ? 1 : 0, (buf[5] & 0x80) ? 1 : 0);
            fflush(stdout);
            ++printed;
        }
        memcpy(prev, buf, read);
    }

    printf("\n  每个字节相对首帧的变化掩码（非零=该字节会变，说明有数据）:\n");
    printf("  字节:  ");
    for (int i = 1; i < 20; ++i) {
        printf("%02d ", i);
    }
    printf("\n  掩码:  ");
    for (int i = 1; i < 20; ++i) {
        printf("%02X ", diffmask[i]);
    }
    printf("\n  首帧:  ");
    for (int i = 1; i < 20 && i < base_len; ++i) {
        printf("%02X ", base[i]);
    }
    printf("\n");

    printf("\n  样本数 = %d\n", samples);
    printf("  按钮字节按位或: b0=0x%02X b1=0x%02X b2=0x%02X\n", or0, or1, or2);
    printf("  -> R(b0.40h)=%d  ZR(b0.80h)=%d  L(b2.40h)=%d  ZL(b2.80h)=%d\n",
           (or0 & 0x40) ? 1 : 0, (or0 & 0x80) ? 1 : 0,
           (or2 & 0x40) ? 1 : 0, (or2 & 0x80) ? 1 : 0);
    printf("  (1 表示手柄确实置上了 SDL3 期望的那一位)\n");
    if (out) {
        fprintf(out, "samples=%d\n", samples);
        fprintf(out, "b0=0x%02X b1=0x%02X b2=0x%02X\n", or0, or1, or2);
        fprintf(out, "R=%d ZR=%d L=%d ZL=%d\n", (or0 & 0x40) ? 1 : 0, (or0 & 0x80) ? 1 : 0,
                (or2 & 0x40) ? 1 : 0, (or2 & 0x80) ? 1 : 0);
        fclose(out);
        printf("\n  结果已写入 hid_dump.txt\n");
    }
    CloseHandle(h);
}

int main(int argc, char **argv) {
    if (argc >= 3) {
        g_vid = (int)strtol(argv[1], NULL, 16);
        g_pid = (int)strtol(argv[2], NULL, 16);
    } else {
        g_vid = 0x057E;
        g_pid = 0;
    }

    GUID hid_guid;
    HidD_GetHidGuid(&hid_guid);

    HDEVINFO info = SetupDiGetClassDevsA(&hid_guid, NULL, NULL,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (info == INVALID_HANDLE_VALUE) {
        printf("SetupDiGetClassDevs failed\n");
        return 1;
    }

    printf("HID devices:\n");
    char chosen[MAX_PATH_BUF] = {0};

    for (DWORD i = 0; i < 64; ++i) {
        SP_DEVICE_INTERFACE_DATA iface;
        iface.cbSize = sizeof(iface);
        if (!SetupDiEnumDeviceInterfaces(info, NULL, &hid_guid, i, &iface)) {
            break;
        }

        DWORD need = 0;
        SetupDiGetDeviceInterfaceDetailA(info, &iface, NULL, 0, &need, NULL);
        if (need == 0) {
            continue;
        }
        SP_DEVICE_INTERFACE_DETAIL_DATA_A *detail =
            (SP_DEVICE_INTERFACE_DETAIL_DATA_A *)malloc(need);
        detail->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_A);
        if (!SetupDiGetDeviceInterfaceDetailA(info, &iface, detail, need, NULL, NULL)) {
            free(detail);
            continue;
        }

        HANDLE h = CreateFileA(detail->DevicePath, 0,
                               FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                               OPEN_EXISTING, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            HIDD_ATTRIBUTES attr;
            attr.Size = sizeof(attr);
            if (HidD_GetAttributes(h, &attr)) {
                printf("  %04X:%04X  %s\n", attr.VendorID, attr.ProductID,
                       detail->DevicePath);
                if (attr.VendorID == g_vid &&
                    (g_pid == 0 || attr.ProductID == g_pid) && chosen[0] == 0) {
                    strncpy(chosen, detail->DevicePath, MAX_PATH_BUF - 1);
                }
            }
            CloseHandle(h);
        }
        free(detail);
    }

    SetupDiDestroyDeviceInfoList(info);

    if (chosen[0] == 0) {
        printf("\nNo device matching %04X:%04X found.\n", g_vid, g_pid);
        return 1;
    }

    printf("\nDumping %04X:%04X:\n", g_vid, g_pid);
    dump_device(chosen);
    printf("\n按回车键退出...\n");
    getchar();
    return 0;
}
