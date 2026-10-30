/*
 * sdl3_bindings.c - ask SDL3 directly what a gamepad exposes.
 *
 * Prints every gamepad binding plus the live value of each axis, which settles
 * whether ZL/ZR are missing from the mapping or simply stuck high.
 *
 *   gcc -O2 -o sdl3_bindings.exe tools/sdl3_bindings.c \
 *       -I .cache/cpm/sdl3/release-3.4.8/include \
 *       -I build-mingw/_deps/sdl3-build/include-revision \
 *       build-mingw/_deps/sdl3-build/libSDL3.a \
 *       -lwinmm -lsetupapi -lhid -limm32 -lole32 -loleaut32 -luuid \
 *       -lgdi32 -luser32 -lshell32 -ladvapi32 -lversion -lbcrypt
 */
#include <SDL3/SDL.h>
#include <stdio.h>

int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    if (!SDL_Init(SDL_INIT_GAMEPAD | SDL_INIT_JOYSTICK)) {
        printf("SDL_Init failed: %s\n", SDL_GetError());
        return 1;
    }

    SDL_SetHint("SDL_JOYSTICK_HIDAPI_SWITCH", "1");

    int count = 0;
    SDL_JoystickID *ids = SDL_GetJoysticks(&count);
    printf("joysticks: %d\n", count);
    for (int i = 0; i < count; ++i) {
        char guid[64];
        SDL_GUIDToString(SDL_GetJoystickGUIDForID(ids[i]), guid, sizeof(guid));
        printf("  id=%u name='%s' guid=%s gamepad=%d\n", ids[i],
               SDL_GetJoystickNameForID(ids[i]), guid,
               SDL_IsGamepad(ids[i]));
    }
    SDL_free(ids);
    if (count == 0) {
        return 1;
    }

    SDL_Joystick *js = SDL_OpenJoystick(1);
    SDL_Gamepad *gp = NULL;
    /* try the first id that reports as a gamepad */
    ids = SDL_GetJoysticks(&count);
    for (int i = 0; i < count; ++i) {
        if (SDL_IsGamepad(ids[i])) {
            gp = SDL_OpenGamepad(ids[i]);
            if (gp) {
                printf("opened gamepad id=%u\n", ids[i]);
                break;
            }
            printf("OpenGamepad(%u) failed: %s\n", ids[i], SDL_GetError());
        }
    }
    SDL_free(ids);

    printf("\njoystick axes = %d buttons = %d\n",
           js ? SDL_GetNumJoystickAxes(js) : -1,
           js ? SDL_GetNumJoystickButtons(js) : -1);
    if (js) {
        for (int a = 0; a < SDL_GetNumJoystickAxes(js); ++a) {
            printf("  joystick axis %d = %d\n", a, SDL_GetJoystickAxis(js, a));
        }
    }

    if (!gp) {
        printf("no gamepad\n");
        return 1;
    }

    printf("\ngamepad name = %s\n", SDL_GetGamepadName(gp));
    char *map = SDL_GetGamepadMapping(gp);
    printf("mapping = %s\n", map ? map : "(none)");
    SDL_free(map);

    int nbind = 0;
    SDL_GamepadBinding **bindings = SDL_GetGamepadBindings(gp, &nbind);
    printf("binding count = %d\n", nbind);
    if (!bindings) {
        printf("SDL_GetGamepadBindings returned NULL: %s\n", SDL_GetError());
    } else {
        printf("bindings:\n");
        for (int i = 0; bindings[i]; ++i) {
            const SDL_GamepadBinding *b = bindings[i];
            switch (b->input_type) {
            case SDL_GAMEPAD_BINDTYPE_BUTTON:
                printf("  input=button%d -> ", b->input.button);
                break;
            case SDL_GAMEPAD_BINDTYPE_AXIS:
                printf("  input=axis%d -> ", b->input.axis.axis);
                break;
            case SDL_GAMEPAD_BINDTYPE_HAT:
                printf("  input=hat%d.%d -> ", b->input.hat.hat, b->input.hat.hat_mask);
                break;
            default:
                printf("  input=? -> ");
                break;
            }
            switch (b->output_type) {
            case SDL_GAMEPAD_BINDTYPE_BUTTON:
                printf("BUTTON %d\n", b->output.button);
                break;
            case SDL_GAMEPAD_BINDTYPE_AXIS:
                printf("AXIS %d (min=%d max=%d)\n", b->output.axis.axis,
                       b->output.axis.axis_min, b->output.axis.axis_max);
                break;
            case SDL_GAMEPAD_BINDTYPE_HAT:
                printf("HAT\n");
                break;
            default:
                printf("?\n");
                break;
            }
        }
        SDL_free(bindings);
    }

    printf("\nlive gamepad axis values (press ZL / ZR now, 20 seconds):\n");
    const char *names[] = {"LEFTX", "LEFTY", "RIGHTX", "RIGHTY",
                           "LEFT_TRIGGER(ZL)", "RIGHT_TRIGGER(ZR)"};
    Uint64 end = SDL_GetTicksNS() + 20000000000ULL;
    Sint16 last[6] = {0};
    int first = 1;
    while (SDL_GetTicksNS() < end) {
        int changed = 0;
        Sint16 cur[6];
        for (int a = 0; a < 6; ++a) {
            cur[a] = SDL_GetGamepadAxis(gp, (SDL_GamepadAxis)a);
            if (cur[a] != last[a]) {
                changed = 1;
            }
        }
        if (changed || first) {
            printf("  raw a4=%6d a5=%6d | ", js ? SDL_GetJoystickAxis(js, 4) : -1,
                   js ? SDL_GetJoystickAxis(js, 5) : -1);
            for (int a = 0; a < 6; ++a) {
                printf("%s=%6d  ", names[a], cur[a]);
            }
            printf("\n");
            for (int a = 0; a < 6; ++a) {
                last[a] = cur[a];
            }
            first = 0;
        }
        SDL_PumpEvents();
        SDL_Delay(20);
    }

    SDL_CloseGamepad(gp);
    if (js) {
        SDL_CloseJoystick(js);
    }
    return 0;
}
