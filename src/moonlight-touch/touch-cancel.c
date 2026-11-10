// SPDX-License-Identifier: MIT
// Surface Overdrive: Moonlight lifts its fingers on the host when the compositor takes them for a gesture.
//
// When KWin takes the touch points of a window for a gesture (the three-finger swipe between desktops) it stops sending
// that window their events: no "up", and no wl_touch.cancel either (seen on the tablet: two fingers down, nothing after).
// Moonlight then never lifted them on the host, which kept them pressed: taps and even mouse moves on the PC turned into
// drags until the stream was closed. And a cancel, when a compositor sends one, SDL3 reports as
// SDL_EVENT_FINGER_CANCELED, which the Flatpak's SDL2 (sdl2-compat) drops: SDL2 has no such event.
//
// Preloaded into Moonlight (LD_PRELOAD), this library keeps the fingers that are down (an SDL3 event watch, which sees an
// event before it is queued and may change it or queue others before it) and lifts on the host those that went quiet:
// - a canceled finger becomes a lifted one;
// - a new finger first lifts the fingers with no news for 150 ms, and a finger down again with the same id (KWin reuses
//   them): their "up" is queued before the new "down";
// - two fingers or more with no news for half a second are lifted (a gesture takes at least two of Moonlight's before
//   KWin knows it is one; two fingers held perfectly still are rare), checked whenever Moonlight asks for events, so the
//   PC is not left with fingers pressed while its mouse is used.
// The watch is put in again (removed first, so never twice) whenever SDL or one of its parts starts or a window is made:
// Moonlight starts and stops SDL more than once (a test decode, then the stream), and quitting SDL drops the watches.
// Window events (focus, hidden) do not come when KWin switches desktops, so they cannot be used.
//
// OVERDRIVE_TOUCH_DEBUG=1 in the environment logs the finger events to stderr.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define SDL_EVENT_FINGER_DOWN 0x700
#define SDL_EVENT_FINGER_UP 0x701
#define SDL_EVENT_FINGER_MOTION 0x702
#define SDL_EVENT_FINGER_CANCELED 0x703

// SDL3's SDL_TouchFingerEvent (SDL_Event is a 128-byte union that starts with it)
struct finger_event {
    uint32_t type;
    uint32_t reserved;
    uint64_t timestamp;
    uint64_t touch_id;
    uint64_t finger_id;
    float x, y, dx, dy, pressure;
    uint32_t window_id;
};
union sdl_event {
    uint32_t type;
    struct finger_event finger;
    uint8_t padding[128];
};

typedef bool (*sdl_event_filter)(void *userdata, void *event);

#define MAX_FINGERS 16
#define STALE_NEW_NS 150000000LL    // quiet this long when another finger comes: lifted
#define STALE_MANY_NS 500000000LL   // two or more quiet this long: lifted
static struct finger_event down[MAX_FINGERS];
static long long seen[MAX_FINGERS];  // last news of each, CLOCK_MONOTONIC ns
static int ndown;
static int debug = -1;
static bool (*push_event)(union sdl_event *);

static long long now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static int find(uint64_t touch, uint64_t finger)
{
    for (int i = 0; i < ndown; i++)
        if (down[i].touch_id == touch && down[i].finger_id == finger)
            return i;
    return -1;
}

static void forget(uint64_t touch, uint64_t finger)
{
    int i = find(touch, finger);
    if (i >= 0) {
        down[i] = down[--ndown];
        seen[i] = seen[ndown];
    }
}

// An "up" for finger i, queued now (the watch sees it and forgets the finger).
static void lift_one(int i, const char *why)
{
    union sdl_event e;
    memset(&e, 0, sizeof(e));
    e.finger = down[i];
    e.finger.type = SDL_EVENT_FINGER_UP;
    e.finger.timestamp = 0;   // SDL stamps it
    e.finger.dx = e.finger.dy = e.finger.pressure = 0;
    if (debug)
        fprintf(stderr, "overdrive touch-cancel: lifting finger %llu (%s)\n", (unsigned long long)e.finger.finger_id, why);
    if (push_event)
        push_event(&e);
    forget(e.finger.touch_id, e.finger.finger_id);   // also when SDL did not take it
}

static bool watch(void *userdata, void *event)
{
    (void)userdata;
    union sdl_event *e = event;
    if (e->type < SDL_EVENT_FINGER_DOWN || e->type > SDL_EVENT_FINGER_CANCELED)
        return true;
    if (debug)
        fprintf(stderr, "overdrive touch-cancel: finger 0x%x id %llu (%d down)\n", e->type,
                (unsigned long long)e->finger.finger_id, ndown);
    if (e->type == SDL_EVENT_FINGER_CANCELED)
        e->type = SDL_EVENT_FINGER_UP;   // the same struct
    long long now = now_ns();
    int i = find(e->finger.touch_id, e->finger.finger_id);
    if (e->type == SDL_EVENT_FINGER_DOWN) {
        // the same id still down, and fingers gone quiet: lifted before this one goes down
        if (i >= 0)
            lift_one(i, "its id is down again");
        for (int k = ndown; k--;)
            if (now - seen[k] > STALE_NEW_NS)
                lift_one(k, "quiet when a new finger came");
        if (ndown < MAX_FINGERS) {
            down[ndown] = e->finger;
            seen[ndown++] = now;
        }
    } else if (e->type == SDL_EVENT_FINGER_UP) {
        forget(e->finger.touch_id, e->finger.finger_id);
    } else if (i >= 0) {
        down[i].x = e->finger.x;
        down[i].y = e->finger.y;
        seen[i] = now;
    }
    return true;
}

// From Moonlight's own calls for events: two fingers or more all quiet for half a second are lifted.
static void lift(void)
{
    if (ndown < 2)
        return;
    long long now = now_ns();
    for (int k = 0; k < ndown; k++)
        if (now - seen[k] < STALE_MANY_NS)
            return;
    for (int k = ndown; k--;)
        lift_one(k, "quiet with others: a gesture took them");
}

static void install(void)
{
    static bool told;
    if (debug < 0)
        debug = getenv("OVERDRIVE_TOUCH_DEBUG") != NULL;
    void *sdl3 = dlopen("libSDL3.so.0", RTLD_NOW | RTLD_NOLOAD);
    if (!sdl3)
        return;
    bool (*add_watch)(sdl_event_filter, void *) = (bool (*)(sdl_event_filter, void *))dlsym(sdl3, "SDL_AddEventWatch");
    void (*remove_watch)(sdl_event_filter, void *) = (void (*)(sdl_event_filter, void *))dlsym(sdl3, "SDL_RemoveEventWatch");
    push_event = (bool (*)(union sdl_event *))dlsym(sdl3, "SDL_PushEvent");
    dlclose(sdl3);   // RTLD_NOLOAD took a reference; SDL3 stays loaded by sdl2-compat
    if (!add_watch || !remove_watch)
        return;
    remove_watch(watch, 0);
    if (add_watch(watch, 0) && !told) {
        told = true;
        fputs("overdrive touch-cancel: fingers taken by a gesture are lifted on the host\n", stderr);
    }
}

#define REAL(name, type) ((type)dlsym(RTLD_NEXT, name))

// SDL2's entry points (sdl2-compat's, found next in the search order).
int SDL_Init(uint32_t flags)
{
    int (*real)(uint32_t) = REAL("SDL_Init", int (*)(uint32_t));
    int ret = real ? real(flags) : -1;
    install();
    return ret;
}

int SDL_InitSubSystem(uint32_t flags)
{
    int (*real)(uint32_t) = REAL("SDL_InitSubSystem", int (*)(uint32_t));
    int ret = real ? real(flags) : -1;
    install();
    return ret;
}

void *SDL_CreateWindow(const char *title, int x, int y, int w, int h, uint32_t flags)
{
    void *(*real)(const char *, int, int, int, int, uint32_t) =
        REAL("SDL_CreateWindow", void *(*)(const char *, int, int, int, int, uint32_t));
    void *window = real ? real(title, x, y, w, h, flags) : NULL;
    install();
    return window;
}

int SDL_PollEvent(void *event)
{
    static int (*real)(void *);
    if (!real)
        real = REAL("SDL_PollEvent", int (*)(void *));
    lift();
    return real ? real(event) : 0;
}

int SDL_WaitEvent(void *event)
{
    static int (*real)(void *);
    if (!real)
        real = REAL("SDL_WaitEvent", int (*)(void *));
    lift();
    return real ? real(event) : 0;
}

int SDL_WaitEventTimeout(void *event, int timeout)
{
    static int (*real)(void *, int);
    if (!real)
        real = REAL("SDL_WaitEventTimeout", int (*)(void *, int));
    lift();
    return real ? real(event, timeout) : 0;
}
