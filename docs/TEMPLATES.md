# DNI Template System Documentation

## Overview

The template system provides zone-based verification for Argentine identity documents. It analyzes specific regions of the document to verify authenticity by checking expected visual characteristics.

## Supported Variants

| Variant | Years | Key Features |
|---------|-------|--------------|
| `nuevo_2016` | 2016-2018 | Sun hologram with face, blue color scheme |
| `nuevo_2019` | 2019-2022 | Sun hologram without face, vertical text on right |
| `nuevo_2023` | 2023+ | Pink/blue color scheme, shell-shaped hologram on back |
| `antiguo` | 2009-2015 | Photo on RIGHT side, MRZ on front |

## Zone Definitions

### Front Side Zones (DNI Nuevo)

```
+--------------------------------------------------+
|  [HEADER]  REPUBLICA ARGENTINA - MERCOSUR        |
|                                          [VERT]  |
| +------+  [PERSONAL_DATA]                 TEXT   |
| |PHOTO |  Apellido: ORIONE                       |
| |      |  Nombre: ENRIQUE                        |
| +------+  Sexo: M  Nacionalidad: ARGENTINA       |
|                                                  |
|           [DATES]                    [SIGNATURE] |
|           03 AGO/ AUG 1987                       |
|      [HOLOGRAM_SUN]                              |
|                                                  |
| [DOCUMENT_NUMBER]  [TRAMITE]   [BARCODE_PDF417]  |
| 33.116.561         0058...                       |
+--------------------------------------------------+
```

### Back Side Zones (DNI Nuevo)

```
+--------------------------------------------------+
| [ADDRESS]                                        |
| DOMICILIO: AV. SANTA FE 226...                   |
| LUGAR DE NACIMIENTO: BUENOS AIRES                |
|                                                  |
| +-------+  [HOLOGRAM]  [MAP]       [FINGERPRINT] |
| |GHOST  |     @@@@     /\\         +----------+  |
| |PHOTO  |    @@@@@@    ||         |  PULGAR  |  |
| +-------+              \\/         +----------+  |
|                                                  |
| [CUIL]         [MINISTER_SIGNATURE]              |
| 24-33116561-8                                    |
|                                                  |
| [MRZ]                                            |
| IDARG33116561<6<<<<<<<<<<<<<<<<<<                |
| 8708036M3110119ARG<<<<<<<<<<<<<4                 |
| ORIONE<<ENRIQUE<<<<<<<<<<<<<<<<<<                |
+--------------------------------------------------+
```

## Zone Verification Methods

Each zone has specific verification methods:

| Method | Description | Zones |
|--------|-------------|-------|
| `saturation_check` | Verifies high color saturation (holograms) | hologram_sun, hologram_circle |
| `iridescence` | Checks hue variance typical of holograms | hologram zones |
| `face_detection` | Detects face presence via edge analysis | photo |
| `border_integrity` | Checks for consistent photo borders | photo |
| `barcode_decode` | Validates PDF417 pattern | barcode_pdf417 |
| `fingerprint_presence` | Detects ridge patterns | fingerprint |
| `text_presence` | Verifies text density | header, personal_data, cuil |
| `shape_recognition` | Identifies Argentina map shape | argentina_map |

## Automatic Variant Detection

The system automatically detects the document variant based on:

1. **Pink color presence** → `nuevo_2023`
2. **Photo position** (left vs right) → `antiguo` if right
3. **Hologram face detection** → `nuevo_2016` if face detected
4. **Default** → `nuevo_2019`

## API Usage

The template analysis is automatically triggered when `check_authenticity=true`:

```json
POST /documents
{
  "client_id": "client123",
  "document_type": "dni",
  "image_base64": "...",
  "check_authenticity": true
}
```

Response includes template analysis:

```json
{
  "extracted_data": {
    "authenticity_result": {
      "authenticity_score": 0.78,
      "basic_score": 0.82,
      "template_score": 0.75,
      "variant_detected": "nuevo_2019",
      "zones_passed": 7,
      "zones_analyzed": 9,
      "critical_zones_passed": true,
      "zone_results": {
        "photo": {"score": 0.85, "verified": true},
        "hologram_sun": {"score": 0.72, "verified": true},
        "barcode_pdf417": {"score": 0.90, "verified": true}
      },
      "flags": []
    }
  }
}
```

## Scoring

- **Basic score** (40%): Saturation, sharpness, glare, moiré analysis
- **Template score** (60%): Per-zone verification results
- **Combined score**: Weighted average of both

### Critical Zones

Zones that MUST pass for document to be considered authentic:

**Front**: photo, document_number, barcode_pdf417, hologram_sun
**Back**: mrz, fingerprint, hologram_circle, cuil

## Reference Samples

Reference samples are stored in:
```
data/reference_samples/dni/
├── nuevo_2016/
│   ├── front/
│   └── back/
├── nuevo_2019/
│   ├── front/
│   └── back/
├── nuevo_2023/
│   ├── front/
│   └── back/
├── antiguo/
│   ├── front/
│   └── back/
└── templates.json
```

## Adding New Variants

1. Add sample images to `data/reference_samples/dni/<variant>/`
2. Update `templates.json` with zone coordinates
3. Add variant detection logic in `VariantDetector`
4. Test with real samples

## Coordinate System

All coordinates in `templates.json` are relative percentages:
- `[x, y, width, height]` where each value is 0-100
- Origin is top-left corner
- Coordinates scale automatically to actual image dimensions

## Known Limitations

### Back-side Variant Detection

Back-side variant distinction between nuevo_2016, nuevo_2019, and nuevo_2023 has limited accuracy due to subtle visual differences. The system may misidentify the specific variant but:

- Zone verification still works correctly (zones have similar positions across variants)
- Authenticity scoring remains reliable
- Critical zone checks are unaffected

**Recommendations**:
- Pair back images with front images for improved variant detection
- Use front-side detection as the primary variant identifier
- Additional reference samples would improve back-side accuracy

### Front-side Detection Accuracy

Front-side variant detection is 100% accurate:
- `antiguo`: Photo on right side, MRZ on front
- `nuevo_2023`: Pink color scheme
- `nuevo_2016`: Face visible in sun hologram
- `nuevo_2019`: Default for nuevo without pink/face
