# Monitor de Sistema

Round 480×480 system monitor: clock, date, and CPU, GPU and RAM cards with
usage bars. A bar and its percentage turn orange from 70 % and red from 85 %.

- Engine: HTML with a native video background (Turing Smart Screen Rev. C
  2.1"/2.8"). The static background is built into `html-monitor-de-sistema.mp4`;
  the clock, date, values and bars are overlays.
- Data: `cpu.usage`, `cpu.temperature`, `gpu.usage`, `gpu.temperature`,
  `memory.used`, `memory.total`, `memory.usage` and the snapshot timestamp.
- Fonts: Inter and JetBrains Mono (latin subset), SIL Open Font License 1.1;
  the licenses are in `fonts/`.
