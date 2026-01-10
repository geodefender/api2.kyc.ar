# KYC Platform - Document OCR Microservice

Arquitectura event-driven para procesamiento OCR de documentos de identidad argentinos (DNI y Pasaporte), diseñada para AWS Lambda + SQS pero simulable completamente en local.

## Arquitectura

```
POST /documents
       ↓
   API Handler (FastAPI)
   - valida request
   - genera IDs
   - persiste en SQLite
   - routea por document_type
       ↓
document.uploaded.v1
       ↓
   Routing por cola
   ├── queue-ocr-dni     → worker-ocr-dni
   └── queue-ocr-passport → worker-ocr-passport
       ↓
   Worker procesa OCR
       ↓
document.extracted.v1
```

## Estructura del Proyecto

```
kyc_platform/
├── api_handler/           # FastAPI Handler (Lambda 1)
│   ├── main.py           # Entrypoint + Mangum handler
│   ├── routes/
│   │   └── documents.py  # POST /documents, GET /documents/{id}
│   ├── services/
│   │   ├── id_generator.py
│   │   └── enqueue.py
│   └── schemas.py
│
├── workers/
│   ├── ocr_dni/          # Worker DNI (Lambda 2)
│   │   ├── lambda_function.py
│   │   ├── processor.py
│   │   └── strategies/
│   │       ├── dni_nuevo.py  # PDF417 + OCR
│   │       └── dni_viejo.py  # OCR puro
│   │
│   └── ocr_passport/     # Worker Passport (Lambda 3)
│       ├── lambda_function.py
│       ├── processor.py
│       └── strategies/
│           └── mrz.py    # MRZ parsing
│
├── queue/                # Abstracción de colas
│   ├── base.py          # Interface EventQueue
│   ├── mock_queue.py    # Implementación local (archivos JSON)
│   └── sqs_queue.py     # Implementación AWS SQS
│
├── contracts/           # Contratos compartidos
│   ├── events.py       # Schemas de eventos versionados
│   └── models.py       # Modelos de dominio
│
├── persistence/         # Capa de persistencia
│   ├── base.py         # Interface DocumentRepository
│   └── sqlite_repository.py  # Implementación SQLite
│
├── runner/
│   └── local_pipeline.py  # Simulación end-to-end
│
└── shared/
    ├── config.py       # Configuración centralizada
    └── logging.py      # Logging estructurado
```

## Correr en Local (Replit)

### 1. Iniciar el API Handler

```bash
python -m kyc_platform.api_handler.main
```

El servidor estará disponible en `http://localhost:5000`

### 2. Probar el endpoint

```bash
# Subir documento DNI
curl -X POST http://localhost:5000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "dni",
    "image": "<base64_image>",
    "client_id": "demo"
  }'

# Consultar estado
curl http://localhost:5000/documents/{document_id}
```

### 3. Simular pipeline completo

```bash
python -m kyc_platform.runner.local_pipeline
```

Este script:
1. Crea una imagen de prueba
2. Simula POST al handler
3. Encola el evento
4. Ejecuta el worker correspondiente
5. Muestra los resultados

## Eventos

### document.uploaded.v1

```json
{
  "event": "document.uploaded.v1",
  "timestamp": "2024-01-15T10:30:00Z",
  "document_id": "doc_1705312200000_abc12345",
  "verification_id": "ver_1705312200000_def67890",
  "client_id": "demo",
  "document_type": "dni",
  "image_ref": "./data/uploads/doc_xxx.jpg"
}
```

### document.extracted.v1

```json
{
  "event": "document.extracted.v1",
  "timestamp": "2024-01-15T10:30:05Z",
  "document_id": "doc_xxx",
  "verification_id": "ver_xxx",
  "document_type": "dni",
  "extracted_data": {
    "numero_documento": "30123456",
    "apellido": "PEREZ",
    "nombre": "JUAN CARLOS",
    "fecha_nacimiento": "15/03/1985"
  },
  "confidence": 0.95,
  "processing_time_ms": 1250
}
```

## Migración a AWS Lambda

### Handler API (api_handler/)

```python
# lambda_function.py ya está listo
from kyc_platform.api_handler.main import handler
# handler es el Mangum wrapper para Lambda
```

Configuración Lambda:
- Runtime: Python 3.11
- Handler: `kyc_platform.api_handler.main.handler`
- Trigger: API Gateway

### Worker DNI (workers/ocr_dni/)

```python
# lambda_function.py ya está listo
from kyc_platform.workers.ocr_dni.lambda_function import handler
```

Configuración Lambda:
- Runtime: Python 3.11
- Handler: `kyc_platform.workers.ocr_dni.lambda_function.handler`
- Trigger: SQS queue `queue-ocr-dni`
- Layer: tesseract-ocr

### Worker Passport (workers/ocr_passport/)

```python
# lambda_function.py ya está listo
from kyc_platform.workers.ocr_passport.lambda_function import handler
```

Configuración Lambda:
- Runtime: Python 3.11
- Handler: `kyc_platform.workers.ocr_passport.lambda_function.handler`
- Trigger: SQS queue `queue-ocr-passport`
- Layer: tesseract-ocr

## Reemplazar MockQueue por SQS

1. Cambiar variable de entorno:
```bash
export KYC_ENVIRONMENT=aws
```

2. El código automáticamente usará `SQSQueue` en lugar de `MockQueue`

3. Crear las colas en AWS:
```bash
aws sqs create-queue --queue-name queue-ocr-dni
aws sqs create-queue --queue-name queue-ocr-passport
aws sqs create-queue --queue-name queue-extracted
```

## Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| KYC_ENVIRONMENT | local | `local` o `aws` |
| QUEUE_DNI_NAME | queue-ocr-dni | Nombre cola DNI |
| QUEUE_PASSPORT_NAME | queue-ocr-passport | Nombre cola Passport |
| QUEUE_EXTRACTED_NAME | queue-extracted | Nombre cola resultados |
| MOCK_QUEUE_DIR | ./data/queues | Directorio colas mock |
| SQLITE_DB_PATH | ./data/kyc.db | Path base de datos |
| UPLOAD_DIR | ./data/uploads | Directorio uploads |
| LOG_LEVEL | INFO | Nivel de logging |

## OCR Capabilities

### DNI Nuevo
- Lectura de código PDF417 (barcode 2D)
- OCR de texto como fallback
- Extrae: número, apellido, nombre, sexo, fechas, CUIL

### DNI Viejo
- OCR puro de texto
- Extrae: número, apellido, nombre, sexo, nacionalidad, fecha nacimiento

### Pasaporte
- Parsing de MRZ (Machine Readable Zone)
- OCR como fallback
- Extrae: número pasaporte, apellido, nombre, nacionalidad, fechas, sexo
