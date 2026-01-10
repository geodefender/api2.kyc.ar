# Simulación de AWS

Este directorio contiene código que **solo corre en desarrollo local** para simular el comportamiento de AWS Lambda + SQS.

## ¿Por qué existe?

En producción (AWS):
- SQS recibe mensajes y dispara Lambdas automáticamente
- Es infraestructura, no código

En desarrollo local:
- Usamos MockQueue (cola en memoria)
- No hay infraestructura que dispare workers
- Este simulador llena ese gap

## Uso

```bash
python simulacion-de-aws/worker_simulator.py
```

O usar el workflow "AWS Simulator" que corre en paralelo al API server.

## ¿Qué hace?

1. Cada 2 segundos revisa las colas:
   - `kyc-ocr-dni`
   - `kyc-ocr-passport`

2. Si hay mensajes, llama al handler correspondiente:
   - `dni_handler()` para DNIs
   - `passport_handler()` para pasaportes

3. Elimina los mensajes procesados de la cola

## Importante

- Este código **no se deploya a AWS**
- Solo simula lo que SQS+Lambda hacen automáticamente
- El código del API Handler permanece intacto y desacoplado
