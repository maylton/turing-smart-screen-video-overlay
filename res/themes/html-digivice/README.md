# Digivice

Retro LCD system monitor on the gray screen of a Digivice: clock, CPU, GPU
and RAM with 16-cell pixel bars, and a status line that blinks
"ALERTA: AQUECIMENTO" when the CPU passes 75 °C or the GPU 80 °C.

- Engine: HTML with a native video background (Turing Smart Screen Rev. C
  2.1"/2.8"). The Digivice image, the static LCD text, the blinking arrow
  and the scanlines are built into `html-digivice.mp4`; the clock, values,
  bars and status line are overlays.
- Font: VT323 (latin subset), SIL Open Font License 1.1; see `fonts/`.
- The background is the first frame of a user-supplied Digivice GIF. The
  artwork belongs to its rights holders and is not covered by this
  project's license.
