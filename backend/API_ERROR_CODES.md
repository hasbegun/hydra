# Hydra API Error Codes Reference

This document lists all HTTP status codes and error responses used by the Hydra backend API.

---

## Standard HTTP Status Codes

### Success Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful, response contains data |
| 201 | Created | Resource created successfully (e.g., custom probe) |
| 204 | No Content | Request successful, no response body (e.g., delete operations) |
| 304 | Not Modified | Resource unchanged, use cached version (ETag match) |

### Client Error Codes

| Code | Status | Description |
|------|--------|-------------|
| 400 | Bad Request | Invalid request data or validation failure |
| 404 | Not Found | Requested resource does not exist |
| 422 | Unprocessable Entity | Request validation failed (Pydantic) |

### Server Error Codes

| Code | Status | Description |
|------|--------|-------------|
| 500 | Internal Server Error | Unexpected server-side error |

---

## Error Response Format

All error responses follow this JSON structure:

```json
{
  "detail": "Human-readable error message"
}
```

For validation errors (422), FastAPI returns:

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error description",
      "type": "error_type"
    }
  ]
}
```

---

## Endpoint-Specific Errors

### Scan Endpoints (`/api/v1/scan`)

#### POST `/start`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 500 | Scan failed to start | `"Failed to start scan: {error}"` |
| 500 | Unexpected error | `"{error_message}"` |

#### GET `/{scan_id}/status`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Scan not found | `"Scan {scan_id} not found"` |

#### POST `/{scan_id}/cancel`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 400 | Scan not running | `"Scan {scan_id} is not running (status: {status})"` |
| 404 | Scan not found | `"Scan {scan_id} not found"` |

#### GET `/{scan_id}/results`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Scan not found | `"Scan {scan_id} not found"` |
| 404 | Results not ready | `"Results not ready for scan {scan_id}"` |

#### GET `/{scan_id}/report`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Scan not found | `"Scan {scan_id} not found"` |
| 404 | Report not found | `"Report not found for scan {scan_id}"` |
| 404 | Report file missing | `"Report file not found: {path}"` |

#### GET `/{scan_id}/report/html`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Scan not found | `"Scan {scan_id} not found"` |
| 404 | Report not found | `"Report not found for scan {scan_id}"` |
| 404 | HTML file missing | `"HTML report file not found: {path}"` |

#### DELETE `/{scan_id}`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 500 | Delete failed | `"Failed to delete scan: {error}"` |

---

### Plugin Endpoints (`/api/v1/plugins`)

#### GET `/generators`, `/probes`, `/detectors`, `/buffs`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 304 | ETag match | No body (use cached response) |
| 500 | Listing failed | `"{error_message}"` |

---

### Custom Probes Endpoints (`/api/v1/probes/custom`)

#### GET `/`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 500 | Listing failed | `"{error_message}"` |

#### GET `/{name}`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 500 | Read failed | `"{error_message}"` |

#### POST `/`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 201 | Success | Returns created probe |
| 400 | Validation failed | `"{validation_error}"` |
| 500 | Create failed | `"{error_message}"` |

#### POST `/validate`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 500 | Validation error | `"{error_message}"` |

#### PUT `/{name}`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Probe not found | `"{error_message}"` |
| 500 | Update failed | `"{error_message}"` |

#### POST `/{name}/deploy`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 400 | Deploy failed | `"{error_message}"` |
| 500 | Unexpected error | `"{error_message}"` |

#### DELETE `/{name}`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 204 | Success | No body |
| 404 | Probe not found | `"{error_message}"` |
| 500 | Delete failed | `"{error_message}"` |

---

### Config Endpoints (`/api/v1/config`)

#### GET `/presets/{preset_name}`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Preset not found | `"Preset '{preset_name}' not found"` |

---

### Workflow Endpoints (`/api/v1/workflow`)

#### GET `/scan/{scan_id}`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Scan not found | `"Scan {scan_id} not found"` |

#### GET `/scan/{scan_id}/hitlog`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Scan/hitlog not found | `"Hitlog not found for scan {scan_id}"` |

#### GET `/scan/{scan_id}/export`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 400 | Export validation failed | `"{error_message}"` |
| 404 | Scan not found | `"Scan {scan_id} not found"` |
| 500 | Export failed | `"Export failed: {error}"` |

---

### Model Endpoints (`/api/v1/generators`)

#### GET `/{generator_type}/models`
| Code | Condition | Detail Message |
|------|-----------|----------------|
| 404 | Unknown generator | `"Unknown generator type: {generator_type}"` |

---

## WebSocket Errors

### `/api/v1/scan/{scan_id}/ws`

WebSocket connections may close with these codes:

| Code | Reason |
|------|--------|
| 1000 | Normal closure (scan completed) |
| 1001 | Going away (client disconnect) |
| 1011 | Server error during scan |

---

## Common Error Scenarios

### 1. Invalid Request Body
```json
// Request with missing required field
POST /api/v1/scan/start
{ "target_type": "ollama" }

// Response (422)
{
  "detail": [
    {
      "loc": ["body", "target_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 2. Resource Not Found
```json
// Request for non-existent scan
GET /api/v1/scan/invalid-uuid/status

// Response (404)
{
  "detail": "Scan invalid-uuid not found"
}
```

### 3. Invalid Operation
```json
// Trying to cancel a completed scan
POST /api/v1/scan/abc-123/cancel

// Response (400)
{
  "detail": "Scan abc-123 is not running (status: completed)"
}
```

### 4. Server Error
```json
// Internal error during plugin listing
GET /api/v1/plugins/probes

// Response (500)
{
  "detail": "Failed to execute garak command: ..."
}
```

---

## Best Practices for Error Handling

### Frontend Error Handling

1. **Always check status codes** before processing response body
2. **Display user-friendly messages** for common errors (404, 400)
3. **Log detailed errors** for debugging (500 errors)
4. **Implement retry logic** for transient failures
5. **Handle WebSocket disconnections** gracefully

### Example Error Handler (Dart)

```dart
void handleApiError(DioException error) {
  final statusCode = error.response?.statusCode;
  final detail = error.response?.data['detail'];

  switch (statusCode) {
    case 400:
      showSnackbar('Invalid request: $detail');
      break;
    case 404:
      showSnackbar('Not found: $detail');
      break;
    case 422:
      showSnackbar('Validation error');
      break;
    case 500:
      showSnackbar('Server error. Please try again.');
      log.error('Server error: $detail');
      break;
    default:
      showSnackbar('An error occurred');
  }
}
```

---

*Last Updated: 2026-01-17*
