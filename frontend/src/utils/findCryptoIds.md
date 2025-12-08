# Как найти ID криптовалют для CryptoIcon

Компонент `CryptoIcon` использует **CoinGecko** как основной источник данных и иконок.

## CoinGecko ID

CoinGecko использует ID как строку (например, "bitcoin", "ethereum"), а не число.

### Способ 1: Через сайт (самый простой)
1. Откройте https://www.coingecko.com
2. Найдите монету через поиск
3. Откройте страницу монеты
4. ID можно найти в URL страницы:
   - Например: `https://www.coingecko.com/en/coins/bitcoin` → ID = `bitcoin`
   - Или: `https://www.coingecko.com/en/coins/ethereum` → ID = `ethereum`

### Способ 2: Через API (не требует API ключа)
```bash
# Получить список всех монет
curl "https://api.coingecko.com/api/v3/coins/list"
```

Ответ будет в формате:
```json
[
  {
    "id": "bitcoin",
    "name": "Bitcoin",
    "symbol": "btc"
  },
  {
    "id": "ethereum",
    "name": "Ethereum",
    "symbol": "eth"
  },
  ...
]
```

### Способ 3: Через поиск на сайте
1. Откройте https://www.coingecko.com
2. Используйте поиск в верхней части страницы
3. Выберите монету из результатов
4. ID будет в URL страницы

## Пример: Добавление новой монеты

Допустим, нужно добавить монету "Example Coin" с символом "EXM":

1. **Найти CoinGecko ID:**
   - Открываем https://www.coingecko.com
   - Ищем "Example Coin"
   - Открываем страницу монеты
   - ID будет в URL: `https://www.coingecko.com/en/coins/example-coin` → ID = `example-coin`

2. **Добавить в код:**
   Откройте `frontend/src/components/CryptoIcon/CryptoIcon.tsx` и добавьте в объект `COINGECKO_IDS`:
   ```typescript
   EXM: 'example-coin',
   ```

## Формат URL иконок

CoinGecko предоставляет иконки по следующим URL:
- `https://assets.coingecko.com/coins/images/{id}/large/{image_name}.png` (высокое качество)
- `https://assets.coingecko.com/coins/images/{id}/small/{image_name}.png` (маленькое качество)

Иконки также доступны через API в поле `image.large` или `image.small`.

## Полезные ссылки

- CoinGecko Website: https://www.coingecko.com
- CoinGecko API Docs: https://www.coingecko.com/en/api/documentation
- CryptoIcons CDN: https://cryptoicons.org (используется как fallback)
