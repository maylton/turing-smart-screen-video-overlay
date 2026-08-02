# Criação de temas HTML em uma IDE

Este guia documenta o contrato público do motor HTML para quem deseja criar,
testar, empacotar e compartilhar temas sem depender exclusivamente do editor
visual. O ponto de partida funcional está em
`res/theme-templates/html-ide-starter/`; o mesmo conteúdo também é distribuído
como o arquivo importável `res/theme-templates/html-ide-starter.theme`.

## Início rápido

1. Importe `html-ide-starter.theme` pelo botão **Importar tema** do editor HTML.
2. Abra a pasta criada em `res/themes/<nome-do-tema>` na sua IDE.
3. Altere o nome em `manifest.json` e edite `index.html`, `style.css`,
   `theme.js` e `overlays.json`.
4. Abra o tema no editor visual para conferir os overlays e salve uma vez para
   regenerar os artefatos derivados.
5. Use **Exportar tema** para gerar um único `.theme` compartilhável.

O importador nunca sobrescreve um tema instalado: nomes repetidos recebem um
sufixo numérico. A exportação também recusa sobrescrever um arquivo existente.

## Estrutura mínima

```text
meu-tema/
├── manifest.json                 # contrato do motor
├── overlays.json                 # fonte canônica dos textos e barras
├── index.html                    # composição visual
├── style.css                     # CSS escrito pelo autor
├── theme.js                      # comportamento opcional do autor
├── theme-editor-overrides.css    # gerado pelo editor
└── theme-editor-widgets.js       # runtime local gerado pelo editor
```

Imagens, fontes e vídeos devem permanecer dentro da pasta do tema e usar
caminhos relativos. Não use links simbólicos: eles são rejeitados na
exportação. `theme-editor-overrides.css`, `theme-editor-widgets.js`, os nós
HTML marcados como gerados e `atomicRegions` são derivados de `overlays.json`;
portanto, não faça alterações permanentes nesses artefatos gerados.

## `manifest.json`

Exemplo mínimo:

```json
{
  "engine": "html",
  "name": "Meu tema",
  "version": 1,
  "display": {"width": 480, "height": 480},
  "refreshRate": 1,
  "entrypoint": "index.html",
  "overlayDocument": "overlays.json",
  "permissions": ["sensors"],
  "network": false,
  "dataUpdateIntervals": {"default": 1},
  "atomicRegions": []
}
```

Campos disponíveis:

- `engine`: deve ser `html`.
- `name`: nome exibido na galeria.
- `version`: inteiro positivo controlado pelo autor.
- `display.width` e `display.height`: dimensões positivas do canvas em pixels.
- `refreshRate`: frequência máxima de renderização, em atualizações por segundo.
- `entrypoint`: HTML local, relativo à raiz do tema.
- `overlayDocument`: quando usado, deve ser exatamente `overlays.json`.
- `permissions`: use `sensors`; permissões desconhecidas não são importadas.
- `network`: mantenha `false`. A galeria atual aplica uma política local e
  rejeita temas HTML com acesso à rede.
- `dataUpdateIntervals.default`: intervalo padrão dos sensores, em segundos.
- `dataUpdateIntervals.<binding>`: intervalo de uma métrica específica, como
  `cpu.usage`; todos os intervalos devem ser maiores que zero.
- `atomicRegions`: áreas retangulares que podem ser atualizadas isoladamente.
  O editor sincroniza uma região `overlay:<id>` para cada elemento visível.
- `nativeVideoOverlay`: contrato opcional de vídeo nativo descrito abaixo.

Todos os caminhos são relativos, não podem escapar da pasta do tema e precisam
apontar para arquivos existentes.

### Vídeo nativo com overlays

O fundo nativo está disponível atualmente para temas 480×480, sem rede e com a
permissão `sensors`:

```json
{
  "nativeVideoOverlay": {
    "enabled": true,
    "localPath": "background.mp4",
    "devicePath": "/mnt/SDCARD/video/background.mp4",
    "fps": 24,
    "duration": 10,
    "backgroundFrame": 0
  }
}
```

- `localPath`: MP4 dentro do tema.
- `devicePath`: destino absoluto seguro no cartão; o nome do arquivo deve ser o
  mesmo de `localPath`.
- `fps`: `24` ou `30`.
- `duration`: maior que zero, no máximo 60 segundos e com um número inteiro de
  quadros (`duration * fps`).
- `backgroundFrame`: instante de um quadro válido, alinhado ao FPS.

Elementos dinâmicos precisam usar `data-turing-overlay`. O seletor é fixo para
que o fundo seja reproduzido pelo hardware enquanto somente textos e barras
são transmitidos como overlays. Gere ou atualize o vídeo pelo editor ou com:

```bash
python3 html-theme-build-video.py --theme res/themes/meu-tema
```

## HTML e segurança

O `index.html` precisa conter uma política CSP local. Use esta base:

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self' data:; script-src 'self'; style-src 'self';
               img-src 'self' data:; font-src 'self'; connect-src 'none';
               media-src 'self'; object-src 'none'; frame-src 'none';
               base-uri 'none'; form-action 'none'">
```

Mantenha JavaScript e CSS em arquivos locais, sem `eval`, código inline,
`fetch`, CDN ou arquivos externos. O runtime bloqueia navegação e recursos que
não pertencem à pasta do tema.

Um elemento HTML escrito pelo autor torna-se overlay ao ter ID único e o
marcador:

```html
<div id="meu-hostname" data-turing-overlay>HOST: --</div>
```

Para elementos gerados, o editor também usa `data-turing-generated-widget`,
`data-turing-binding`, `data-turing-format` e `data-turing-kind`. Deixe o editor
gerar esse bloco a partir de `overlays.json`.

## API JavaScript

Cada snapshot recebido possui a seguinte estrutura:

```js
{
  schemaVersion: 1,
  timestamp: 1785654000.0,
  sequence: 42,
  data: {cpu: {}, gpu: {}, memory: {}, disk: {}, network: {}, system: {}, weather: {}},
  errors: {}
}
```

Há duas formas públicas e equivalentes de consumir a atualização:

```js
// Opção 1: um hook único. O runtime gerado preserva e encadeia esta função.
window.TuringTheme = {
  update(snapshot) {
    document.getElementById('meu-hostname').textContent =
      snapshot.data.system?.hostname ?? '--';
  }
};

// Opção 2: evento para componentes independentes.
window.addEventListener('turing-snapshot', event => {
  const snapshot = event.detail;
});
```

Use `textContent`, nunca `innerHTML`, para valores de sensores. Não leia o
sistema operacional e não faça polling: o aplicativo coleta e agenda os dados.
O arquivo `theme.js` do template inclui exemplos comentados das funções
`valueAt(snapshot, binding)`, `setText(id, value, fallback)` e `update(snapshot)`.

## Bindings disponíveis

Um binding é um caminho pontuado dentro de `snapshot.data`. `$timestamp` é o
único binding especial e aponta para o timestamp do snapshot.

| Seção | Bindings |
| --- | --- |
| CPU | `cpu.usage`, `cpu.temperature`, `cpu.frequency`, `cpu.load.0`, `cpu.load.1`, `cpu.load.2`, `cpu.logicalCores`, `cpu.physicalCores` |
| GPU | `gpu.available`, `gpu.name`, `gpu.usage`, `gpu.temperature`, `gpu.frequency`, `gpu.fan`, `gpu.fps`, `gpu.vramUsage`, `gpu.vramUsed`, `gpu.vramTotal`, `gpu.selectedIndex` |
| Memória | `memory.usage`, `memory.used`, `memory.available`, `memory.total`, `memory.swapUsage`, `memory.swapUsed`, `memory.swapTotal` |
| Disco | `disk.mount`, `disk.usage`, `disk.used`, `disk.free`, `disk.total` |
| Rede selecionada | `network.interface`, `network.upload`, `network.download`, `network.uploaded`, `network.downloaded` |
| Sistema | `system.hostname`, `system.platform`, `system.platformRelease`, `system.architecture`, `system.time`, `system.uptime` |
| Clima | `weather.temperature`, `weather.feelsLike`, `weather.description`, `weather.humidity`, `weather.updatedAt`, `weather.provider` |
| Especial | `$timestamp` |

Temperaturas, GPU e clima podem ser `null` quando o hardware ou provedor não
oferece o dado. O runtime mostra o fallback do formatador. Upload/download usam
MiB/s; totais de rede usam bytes; memória, VRAM e disco usam GiB.

## `overlays.json`

O envelope atual é fixo:

```json
{
  "format": "turing-html-overlays",
  "formatVersion": 1,
  "schemaVersion": 5,
  "display": {"width": 480, "height": 480},
  "elements": []
}
```

Cada item de `elements` aceita:

- `id`: ID HTML único; começa com letra e usa letras, números, `_` ou `-`.
- `x`, `y`, `width`, `height`: retângulo positivo dentro do display.
- `fontSize`: 6–160 px.
- `color`: cor `#rrggbb`.
- `fontWeight`: `0` para herdar, ou 100–900 em passos de 100.
- `textAlign`: `inherit`, `left`, `center` ou `right`.
- `opacity`: 0–100.
- `zIndex`: 1–9999.
- `visible`: controla renderização e região atômica.
- `componentType`: chave opcional do catálogo do editor.
- `generatedWidget`: `true` para o editor controlar o nó HTML.
- `binding`: caminho seguro listado acima.
- `formatter`: formatador local listado abaixo.
- `sample`: texto de preview com 1–80 caracteres; barras usam número 0–100.
- `elementKind`: `text` ou `bar`; barras exigem `bar-percent`.
- `effectsManaged`: permite ao editor gerar os efeitos CSS.
- `gradientEnabled`, `gradientStartColor`, `gradientEndColor` e
  `gradientDirection` (`horizontal`, `vertical` ou `diagonal`).
- `outlineWidth` (0–8) e `outlineColor`.
- `glowRadius` (0–40) e `glowColor`.

`componentType` pode usar `cpu-temperature`, `gpu-temperature`, `cpu-usage`,
`gpu-usage`, `ram-usage`, `ram-used`, `cpu-load`, `disk-usage`,
`weather-temperature`, `weather-condition`, `time`, `date` e as barras
`cpu-usage-bar`, `gpu-usage-bar`, `ram-usage-bar`, `disk-usage-bar`,
`cpu-temperature-bar`, `gpu-temperature-bar`. Para outros bindings, deixe
`componentType` vazio e informe binding, formatter, amostra e tipo.

Formatadores aceitos:

| Formatador | Resultado esperado |
| --- | --- |
| `text` | texto ou `--` |
| `integer` | inteiro arredondado |
| `decimal` | duas casas decimais |
| `percent` | percentual limitado a 0–100 |
| `temperature` | graus Celsius |
| `gigabytes` | GiB exibidos como GB |
| `megabytes` | valor em MiB |
| `gigahertz` | valor já expresso em GHz |
| `gigahertz-from-megahertz` | converte MHz em GHz |
| `megabytes-per-second` | taxa em MB/s |
| `bytes` | escala B, KB, MB, GB ou TB |
| `duration` | segundos em `H:MM:SS` |
| `fps` | quadros por segundo |
| `load` | carga com duas casas |
| `time` | hora `HH:MM` |
| `date` | data local baseada no timestamp |
| `bar-percent` | preenchimento de barra entre 0 e 100 |

Veja `docs/HTML_OVERLAY_DOCUMENT.md` para o contrato canônico e o
`overlays.json` do template para quatro exemplos completos.

## Converter temas YAML

O conversor preserva o YAML original e pode criar uma pasta HTML editável ou
um pacote único:

```bash
python3 theme-migrate.py analyze res/themes/24
python3 theme-migrate.py convert res/themes/24 ~/Downloads/24-html.theme
python3 theme-migrate.py batch res/themes ~/Downloads/temas-html-convertidos
```

Use `--allow-partial` somente quando aceitar que radiais, históricos ou dados
sem adapter sejam registrados como pendências no `migration-report.json`.
Sempre compare visualmente o resultado e teste no dispositivo antes de remover
o tema YAML.

## Validar, testar e publicar

Validação rápida durante a edição:

```bash
python3 -m json.tool res/themes/meu-tema/manifest.json >/dev/null
python3 -m json.tool res/themes/meu-tema/overlays.json >/dev/null
python3 - <<'PY'
from pathlib import Path
from library.html_theme_visual_editor import load_visual_styles
from library.theme_engine import ThemeManifest

manifest = ThemeManifest.load(Path('res/themes/meu-tema'))
styles = load_visual_styles(manifest)
print(f'{manifest.name}: {len(styles)} overlays válidos')
PY
```

Depois, abra a preview/editor, salve, gere o vídeo quando aplicável e execute o
monitor físico. Exporte um `.theme`, importe-o com outro nome e faça um teste
final dessa cópia; assim também são testados o descritor e a portabilidade.

Para publicar pelo Git:

```bash
git switch -c theme/meu-tema
git add res/themes/meu-tema
git commit -m "Add meu tema HTML"
git push -u origin theme/meu-tema
```

Não publique chaves, caminhos pessoais, caches, backups do editor ou vídeos
fora da licença permitida. Inclua nome, autor, versão, licença dos assets,
resolução, screenshot e instruções de uso no README do tema.
