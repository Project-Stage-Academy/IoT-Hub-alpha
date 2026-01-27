# Grafana Provisioning - Architecture

## 📌 Як UID працює

### UID (Unique Identifier) в Grafana

Кожен datasource та дашборд в Grafana має унікальний ID. Це може бути:
1. **Автоматично генерований UUID** (випадковий) - `cfbfgqadax728c`
2. **Явно встановлений UID** (передбачувальний) - `prometheus-iot-hub`

### Проблема з автоматичним UUID

```yaml
# Старий підхід - проблемний:
datasources:
  - name: Prometheus
    # uid НЕ встановлений → Grafana генерує випадковий
    # Результат: abc123xyz на одній машині, def456uvw на іншій
```

Дашборд посилається на `cfbfgqadax728c`, але на новій машині datasource матиме інший uid → **"No data" error**

### ✅ Рішення: Явно встановлений UID

```yaml
# Новий підхід - правильний:
datasources:
  - name: Prometheus
    uid: prometheus-iot-hub  # ← Явно встановлений
    # Результат: один і той же uid всюди
```

Дашборд посилається на `prometheus-iot-hub` → **завжди працює**

---

## 📁 Файлова структура

```
devops/grafana/provisioning/
├── datasources/
│   └── prometheus.yml
│       ├── name: Prometheus
│       ├── uid: prometheus-iot-hub   ← ЯВНО встановлений
│       └── url: http://prometheus:9090
│
└── dashboards/
    ├── dashboards.yml
    │   └── path: /etc/grafana/provisioning/dashboards
    │
    └── grafana-dashboard.json
        └── panels[*].datasource.uid: "prometheus-iot-hub"  ← Посилання
```

---

## 🔄 Как це працює при старті контейнера

### 1️⃣ Docker Compose запускає Grafana

```yaml
volumes:
  - ./devops/grafana/provisioning/datasources:/etc/grafana/provisioning/datasources:ro
  - ./devops/grafana/provisioning/dashboards:/etc/grafana/provisioning/dashboards:ro
```

### 2️⃣ Grafana прочитує конфіги

- Читає `datasources/prometheus.yml`
- Створює datasource з uid `prometheus-iot-hub`

### 3️⃣ Grafana імпортує дашборди

- Читає `dashboards/dashboards.yml`
- Завантажує JSON файли з папки
- Дашборд посилається на datasource с uid `prometheus-iot-hub`
- **Знаходить датасорс** ✅

---

## 🚀 Переносимість між машинами

### Сценарій: Запуск на новій машині

```bash
# Нова машина
$ docker compose up -d grafana

# Що відбувається:
1. Контейнер стартує
2. Читає devops/grafana/provisioning/datasources/prometheus.yml
3. Створює Prometheus datasource з uid: prometheus-iot-hub
4. Читає devops/grafana/provisioning/dashboards/dashboards.yml
5. Імпортує grafana-dashboard.json
6. Дашборд знаходить datasource по uid: prometheus-iot-hub
7. Все працює! ✅
```

**Без явного UID**, п. 3 створив би інший uid → дашборд не знайшов би datasource → No data

---

## 📋 Контрольний список

- [x] datasources/prometheus.yml має явний uid
- [x] grafana-dashboard.json посилається на той самий uid
- [x] docker-compose.yml змонтовує provisioning папки
- [x] Файли передаються як read-only (:ro)
- [x] Документація актуальна

---

## 💡 Best Practices

1. **Завжди встановлюйте явний UID** у datasources конфігах
2. **Використовуйте описові імена**: `prometheus-iot-hub`, не `ds-1`
3. **Перевірте консистентність** между файлами перед commit
4. **Версіонуйте** UID разом з конфігами

---

## 🔍 Перевірка

```bash
# На будь-якій машині:
curl -u admin:admin http://localhost:3000/api/datasources | jq '.[].uid'
# Результат: prometheus-iot-hub ✅

# Перевірка дашборда:
curl -u admin:admin http://localhost:3000/api/dashboards/uid/iot-hub-alpha-observability | \
  jq '.dashboard.panels[0].datasource.uid'
# Результат: prometheus-iot-hub ✅
```

---

**Остання оновлення**: 2026-01-27
**Статус**: ✅ Production Ready - Fully Portable