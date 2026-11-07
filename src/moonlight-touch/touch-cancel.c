// SPDX-License-Identifier: MIT
// Surface Overdrive: lifted fingers reach Moonlight's host even when the compositor cancels the touch.
//
// KWin cancels the touch points of a window when it takes a gesture (the three-finger swipe between desktops). SDL3 turns
// that into SDL_EVENT_FINGER_CANCELED, which sdl2-compat (Moonlight uses SDL2's API, the Flatpak's SDL2 is sdl2-compat)
// drops: SDL2 has no such event. Moonlight then never sends the fingers up, the host keeps them pressed, and taps and
// even mouse moves on the PC turned into drags until the stream was closed.
//
// Preloaded into Moonlight (LD_PRELOAD), this adds an SDL3 event watch after SDL starts that turns a canceled finger into
// a lifted one. Event watches see an event after the filter and before it is queued, and may change it.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#define SDL_EVENT_FINGER_UP 0x701
#define SDL_EVENT_FINGER_CANCELED 0x703

typedef bool (*sdl_event_filter)(void *userdata, void *event);

static bool watch(void *userdata, void *event)
{
    (void)userdata;
    uint32_t *type = event;   // SDL_Event begins with its type, a 32-bit enum
    if (*type == SDL_EVENT_FINGER_CANCELED)
        *type = SDL_EVENT_FINGER_UP;   // the same struct, SDL_TouchFingerEvent
    return true;
}

static void install(void)
{
    static bool done;
    if (done)
        return;
    void *sdl3 = dlopen("libSDL3.so.0", RTLD_NOW | RTLD_NOLOAD);
    if (!sdl3)
        return;
    bool (*add_watch)(sdl_event_filter, void *) = (bool (*)(sdl_event_filter, void *))dlsym(sdl3, "SDL_AddEventWatch");
    if (add_watch && add_watch(watch, 0)) {
        done = true;
        fputs("overdrive touch-cancel: canceled fingers are sent as lifted\n", stderr);
    }
}

// SDL2's entry points (sdl2-compat's, found next in the search order); the watch goes in once SDL3 is loaded and started.
int SDL_Init(uint32_t flags)
{
    int (*real)(uint32_t) = (int (*)(uint32_t))dlsym(RTLD_NEXT, "SDL_Init");
    int ret = real ? real(flags) : -1;
    install();
    return ret;
}

int SDL_InitSubSystem(uint32_t flags)
{
    int (*real)(uint32_t) = (int (*)(uint32_t))dlsym(RTLD_NEXT, "SDL_InitSubSystem");
    int ret = real ? real(flags) : -1;
    install();
    return ret;
}
