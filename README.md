# CGESP Weather Scraper for Home Assistant

Este addon faz scraping de dados meteorológicos do site da CGESP usando o código numérico da estação.

## Estações Disponíveis

| Código | Nome da Estação |
|--------|-----------------|
| 1000840 | Ipiranga - Ribeirão dos Meninos |
| 1000839 | Cidade Universitária |
| 1000838 | Morumbi - USP |
| 1000837 | Vila Maria |
| 1000836 | Santana |
| 1000835 | Sé - Centro |
| 1000834 | Vila Prudente |
| 1000833 | Itaim Paulista |
| 1000832 | Jardim São Luís |
| 1000831 | Capela do Socorro |
| 1000830 | Parelheiros |

## Instalação

1. Adicione este repositório à loja de addons do Home Assistant
2. Instale o addon "CGESP Weather Scraper"
3. Configure com seu token de API do Home Assistant
4. Opcional: Altere o código da estação nas configurações

## Configuração

- `station_code`: Código da estação (padrão: "1000840" - Ipiranga)
- `scan_interval`: Intervalo de varredura em segundos (padrão: 3600)
- `ha_token`: Token de API do Home Assistant (obrigatório)

## Entidades Criadas

Para cada estação, serão criadas entidades como:
- `sensor.cgesp_1000840_temperature`
- `sensor.cgesp_1000840_humidity`
- `sensor.cgesp_1000840_rain`
- etc...