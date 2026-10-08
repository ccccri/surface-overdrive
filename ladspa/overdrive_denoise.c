// SPDX-License-Identifier: MIT
/*
 * overdrive_denoise: noise suppression for a microphone as a LADSPA plugin, so that PipeWire can run it inside the microphone
 * device itself (no extra "filtered" microphone in the list of devices). The work is done by the rnnoise library; this file only
 * cuts the stream into the 10 ms frames rnnoise wants and mixes its result with the untouched sound.
 *
 * Ports: Input, Output (audio, one channel, 48 kHz) and Strength (0 = untouched, 1 = fully suppressed). The output is 10 ms late.
 */
#include <ladspa.h>
#include <rnnoise.h>
#include <stdlib.h>
#include <string.h>

#define FRAME 480
#define SCALE 32768.0f

enum { PORT_IN, PORT_OUT, PORT_STRENGTH, PORTS };

struct denoise {
	DenoiseState *state;
	LADSPA_Data *port[PORTS];
	float in[FRAME];
	float out[FRAME];
	int fill;
};

static LADSPA_Handle instantiate(const LADSPA_Descriptor *descriptor, unsigned long rate)
{
	struct denoise *d = calloc(1, sizeof(*d));

	(void)descriptor;
	(void)rate;
	if (!d)
		return NULL;
	d->state = rnnoise_create(NULL);
	if (!d->state) {
		free(d);
		return NULL;
	}
	return d;
}

static void connect_port(LADSPA_Handle handle, unsigned long port, LADSPA_Data *data)
{
	struct denoise *d = handle;

	if (port < PORTS)
		d->port[port] = data;
}

static void activate(LADSPA_Handle handle)
{
	struct denoise *d = handle;

	memset(d->in, 0, sizeof(d->in));
	memset(d->out, 0, sizeof(d->out));
	d->fill = 0;
}

static void run(LADSPA_Handle handle, unsigned long count)
{
	struct denoise *d = handle;
	const LADSPA_Data *in = d->port[PORT_IN];
	LADSPA_Data *out = d->port[PORT_OUT];
	float strength = d->port[PORT_STRENGTH] ? *d->port[PORT_STRENGTH] : 1.0f;
	float clean[FRAME];
	unsigned long i;
	int k;

	if (!in || !out)
		return;
	if (!(strength >= 0.0f))
		strength = 0.0f;
	if (strength > 1.0f)
		strength = 1.0f;
	for (i = 0; i < count; i++) {
		float sample = in[i];

		out[i] = d->out[d->fill];
		d->in[d->fill] = (sample == sample ? sample : 0.0f) * SCALE;
		if (++d->fill < FRAME)
			continue;
		d->fill = 0;
		rnnoise_process_frame(d->state, clean, d->in);
		for (k = 0; k < FRAME; k++)
			d->out[k] = (strength * clean[k] + (1.0f - strength) * d->in[k]) / SCALE;
	}
}

static void cleanup(LADSPA_Handle handle)
{
	struct denoise *d = handle;

	rnnoise_destroy(d->state);
	free(d);
}

static const LADSPA_PortDescriptor port_kinds[PORTS] = {
	LADSPA_PORT_INPUT | LADSPA_PORT_AUDIO,
	LADSPA_PORT_OUTPUT | LADSPA_PORT_AUDIO,
	LADSPA_PORT_INPUT | LADSPA_PORT_CONTROL,
};

static const char *const port_names[PORTS] = { "Input", "Output", "Strength" };

static const LADSPA_PortRangeHint port_hints[PORTS] = {
	{ 0, 0.0f, 0.0f },
	{ 0, 0.0f, 0.0f },
	{ LADSPA_HINT_BOUNDED_BELOW | LADSPA_HINT_BOUNDED_ABOVE | LADSPA_HINT_DEFAULT_MAXIMUM, 0.0f, 1.0f },
};

static const LADSPA_Descriptor descriptor = {
	.UniqueID = 0x534f4401,
	.Label = "overdrive_denoise",
	.Properties = 0,
	.Name = "Surface Overdrive microphone noise suppression (rnnoise)",
	.Maker = "Surface Overdrive",
	.Copyright = "MIT",
	.PortCount = PORTS,
	.PortDescriptors = port_kinds,
	.PortNames = port_names,
	.PortRangeHints = port_hints,
	.instantiate = instantiate,
	.connect_port = connect_port,
	.activate = activate,
	.run = run,
	.cleanup = cleanup,
};

const LADSPA_Descriptor *ladspa_descriptor(unsigned long index)
{
	return index == 0 ? &descriptor : NULL;
}
