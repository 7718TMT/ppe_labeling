# API reference

<!-- BEGIN GENERATED NOTICE -->
> **Generated file — do not edit by hand.**
> Produced by `backend/scripts/generate_docs.py` from `backend/app/main.py`, `backend/app/api/`.
> Regenerate after changing those sources; edit the generator scripts, not this file.
> Run `uv run python -m backend.scripts.generate_docs`.
>
> Generated 2026-10-30 at commit `4d2ea6fc58f9`.
> Commit identifies the checkout; output may include uncommitted source changes.
<!-- END GENERATED NOTICE -->

Generated from `create_app().openapi()` without requests, worker startup or model
loading. The schema is used in memory; no OpenAPI JSON file is published.
Only declared parameters, bodies and responses are listed; runtime errors can
include additional cases. See [operations](OPERATIONS.md) for partial-operation
errors. The application currently has no API authentication; CORS is not access
control. Restrict access to a trusted local environment.

Regenerate with `uv run python -m backend.scripts.generate_docs`.

<!-- BEGIN GENERATED -->
## GET `/api/v1/behavior-inference`

Workspace

Return inference videos, jobs, and fixed-model identity.

```json
{
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Workspace Api V1 Behavior Inference Get",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    }
  }
}
```

## POST `/api/v1/behavior-inference/videos`

Import Videos

Import videos and queue fixed-model behavior inference.

```json
{
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_import_videos_api_v1_behavior_inference_videos_post"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Import Videos Api V1 Behavior Inference Videos Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/behavior-inference/videos/{video_id}/results`

Results

Return raw windows and smoothed events for one inference video.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Results Api V1 Behavior Inference Videos  Video Id  Results Get",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/tasks`

Get Tasks

```json
{
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/TaskInfo"
            },
            "title": "Response Get Tasks Api V1 Tasks Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    }
  }
}
```

## POST `/api/v1/tasks/{task}/auto-label`

Auto Label Task All

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/tasks/{task}/export`

Export Task All

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {}
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/tasks/{task}/images`

Get Task Images

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/ImageItem"
            },
            "title": "Response Get Task Images Api V1 Tasks  Task  Images Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/tasks/{task}/images/upload`

Upload Task Images

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_upload_task_images_api_v1_tasks__task__images_upload_post"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## DELETE `/api/v1/tasks/{task}/images/{filename}`

Delete Task Image

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "filename",
      "required": true,
      "schema": {
        "title": "Filename",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/tasks/{task}/images/{filename}/approve`

Approve Task Image

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "filename",
      "required": true,
      "schema": {
        "title": "Filename",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ApprovePayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/tasks/{task}/images/{filename}/auto-label`

Auto Label Task Image

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "filename",
      "required": true,
      "schema": {
        "title": "Filename",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/tasks/{task}/images/{filename}/export`

Export Task Image

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "filename",
      "required": true,
      "schema": {
        "title": "Filename",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {}
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/tasks/{task}/images/{filename}/labels`

Get Task Labels

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "filename",
      "required": true,
      "schema": {
        "title": "Filename",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/LabelResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/tasks/{task}/images/{filename}/labels`

Update Task Labels

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "filename",
      "required": true,
      "schema": {
        "title": "Filename",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/LabelPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/tasks/{task}/inference`

List Inference Items

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/InferenceMediaItem"
            },
            "title": "Response List Inference Items Api V1 Tasks  Task  Inference Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/tasks/{task}/inference`

Upload Inference Media

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_upload_inference_media_api_v1_tasks__task__inference_post"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/InferenceMediaItem"
            },
            "title": "Response Upload Inference Media Api V1 Tasks  Task  Inference Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## DELETE `/api/v1/tasks/{task}/inference/{item_id}`

Delete Inference Item

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "item_id",
      "required": true,
      "schema": {
        "title": "Item Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/tasks/{task}/inference/{item_id}/{variant}`

Get Inference Media

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "item_id",
      "required": true,
      "schema": {
        "title": "Item Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "variant",
      "required": true,
      "schema": {
        "title": "Variant",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/tasks/{task}/rename-sequential`

Rename Task Sequential

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/tasks/{task}/visualizations`

Generate Task Visualizations

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "task",
      "required": true,
      "schema": {
        "title": "Task",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/OperationResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects`

List Projects

```json
{
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response List Projects Api V1 Video Projects Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    }
  }
}
```

## POST `/api/v1/video-projects`

Create Project

```json
{
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ProjectCreate"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Create Project Api V1 Video Projects Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}`

Get Project

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Get Project Api V1 Video Projects  Project Id  Get",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/video-projects/{project_id}/config`

Update Project

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ProjectConfigUpdate"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Update Project Api V1 Video Projects  Project Id  Config Put",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/events`

Workspace Events

Stream durable workspace events, with cursor-based reconnection support.

HTTP mutations remain REST calls. SSE is intentionally one-way: it removes
repeated full-project polling while retaining standard EventSource retries.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "after",
      "required": false,
      "schema": {
        "default": 0,
        "minimum": 0,
        "title": "After",
        "type": "integer"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {}
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/exports`

List Exports

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response List Exports Api V1 Video Projects  Project Id  Exports Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/exports`

Create Export

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Create Export Api V1 Video Projects  Project Id  Exports Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/exports/validate`

Validate Export

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            "title": "Response Validate Export Api V1 Video Projects  Project Id  Exports Validate Get",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/exports/{export_id}/download`

Download Export Archive

Download a completed export snapshot as one ZIP file.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "export_id",
      "required": true,
      "schema": {
        "title": "Export Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {}
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/exports/{export_id}/files/{filename}`

Download Export

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "export_id",
      "required": true,
      "schema": {
        "title": "Export Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "filename",
      "required": true,
      "schema": {
        "title": "Filename",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {}
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/jobs`

List Jobs

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/ProcessingJobResponse"
            },
            "title": "Response List Jobs Api V1 Video Projects  Project Id  Jobs Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/jobs/{job_id}/control`

Control Job

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "job_id",
      "required": true,
      "schema": {
        "title": "Job Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/JobControl"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/ProcessingJobResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/models`

List Models

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response List Models Api V1 Video Projects  Project Id  Models Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/models/import`

Import Model

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_import_model_api_v1_video_projects__project_id__models_import_post"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Import Model Api V1 Video Projects  Project Id  Models Import Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/models/{model_id}/activate`

Activate Model

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "model_id",
      "required": true,
      "schema": {
        "title": "Model Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Activate Model Api V1 Video Projects  Project Id  Models  Model Id  Activate Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/models/{model_id}/unload`

Unload Model

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "model_id",
      "required": true,
      "schema": {
        "title": "Model Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Unload Model Api V1 Video Projects  Project Id  Models  Model Id  Unload Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/processing-options`

Processing Options

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/ProcessingOptionsResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/threshold-profiles`

List Profiles

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response List Profiles Api V1 Video Projects  Project Id  Threshold Profiles Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/threshold-profiles`

Save Profile

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ThresholdProfilePayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Save Profile Api V1 Video Projects  Project Id  Threshold Profiles Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/threshold-profiles/restore-default`

Restore Profile

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Restore Profile Api V1 Video Projects  Project Id  Threshold Profiles Restore Default Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos`

List Videos

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "status",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Status"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response List Videos Api V1 Video Projects  Project Id  Videos Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/import`

Import Videos

Import videos and immediately queue the processing pipeline.

The ``mode`` parameter (``threshold`` or ``model``) controls which suggestion
source is generated after pose tracking completes. Defaults to ``threshold``.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "mode",
      "required": false,
      "schema": {
        "default": "threshold",
        "title": "Mode",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "multipart/form-data": {
        "schema": {
          "$ref": "#/components/schemas/Body_import_videos_api_v1_video_projects__project_id__videos_import_post"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Import Videos Api V1 Video Projects  Project Id  Videos Import Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/rename`

Rename Videos

Rename every video display name in a project with one prefix.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/VideoRenamePayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Rename Videos Api V1 Video Projects  Project Id  Videos Rename Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## DELETE `/api/v1/video-projects/{project_id}/videos/{video_id}`

Delete Video

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/VideoDeleteResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}`

Get Video

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Get Video Api V1 Video Projects  Project Id  Videos  Video Id  Get",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/annotation-derivatives/refresh`

Refresh Annotation Derivatives

Refresh training/export derivatives without generating suggestions.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/AnnotationDerivativeRefreshResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/approve`

Approve Video

Mark a video as approved after validation.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Approve Video Api V1 Video Projects  Project Id  Videos  Video Id  Approve Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/features`

Inspect Features

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "track_id",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "title": "Track Id"
      }
    },
    {
      "in": "query",
      "name": "start",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "title": "Start"
      }
    },
    {
      "in": "query",
      "name": "end",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "title": "End"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Inspect Features Api V1 Video Projects  Project Id  Videos  Video Id  Features Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/features/generate`

Generate Features

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Generate Features Api V1 Video Projects  Project Id  Videos  Video Id  Features Generate Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/history`

Annotation History

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Annotation History Api V1 Video Projects  Project Id  Videos  Video Id  History Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/history/{action}`

History Action

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "action",
      "required": true,
      "schema": {
        "title": "Action",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/RevisionPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response History Action Api V1 Video Projects  Project Id  Videos  Video Id  History  Action  Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/video-projects/{project_id}/videos/{video_id}/inclusion`

Set Video Inclusion

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/InclusionPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Set Video Inclusion Api V1 Video Projects  Project Id  Videos  Video Id  Inclusion Put",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/media`

Video Media

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {}
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/models/{model_id}/infer`

Infer Model

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "model_id",
      "required": true,
      "schema": {
        "title": "Model Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Infer Model Api V1 Video Projects  Project Id  Videos  Video Id  Models  Model Id  Infer Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/overlay`

Video Overlay

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "start",
      "required": true,
      "schema": {
        "minimum": 0,
        "title": "Start",
        "type": "integer"
      }
    },
    {
      "in": "query",
      "name": "end",
      "required": true,
      "schema": {
        "minimum": 0,
        "title": "End",
        "type": "integer"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Video Overlay Api V1 Video Projects  Project Id  Videos  Video Id  Overlay Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/process`

Process Video

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ProcessRequest"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/ProcessingJobResponse"
            },
            "title": "Response Process Video Api V1 Video Projects  Project Id  Videos  Video Id  Process Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/queue`

Queue Video

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/QueueRequest"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "$ref": "#/components/schemas/ProcessingJobResponse"
            },
            "title": "Response Queue Video Api V1 Video Projects  Project Id  Videos  Video Id  Queue Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/segments`

List Segments

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "track_id",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "title": "Track Id"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response List Segments Api V1 Video Projects  Project Id  Videos  Video Id  Segments Get",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/segments`

Create Segment

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/SegmentWrite"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Create Segment Api V1 Video Projects  Project Id  Videos  Video Id  Segments Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/segments/merge`

Merge Segments

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/SegmentMergePayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Merge Segments Api V1 Video Projects  Project Id  Videos  Video Id  Segments Merge Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## DELETE `/api/v1/video-projects/{project_id}/videos/{video_id}/segments/{segment_id}`

Delete Segment

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "segment_id",
      "required": true,
      "schema": {
        "title": "Segment Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/RevisionPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Delete Segment Api V1 Video Projects  Project Id  Videos  Video Id  Segments  Segment Id  Delete",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/video-projects/{project_id}/videos/{video_id}/segments/{segment_id}`

Update Segment

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "segment_id",
      "required": true,
      "schema": {
        "title": "Segment Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/SegmentWrite"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Update Segment Api V1 Video Projects  Project Id  Videos  Video Id  Segments  Segment Id  Put",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/segments/{segment_id}/extend`

Extend Segment

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "segment_id",
      "required": true,
      "schema": {
        "title": "Segment Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/RevisionPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Extend Segment Api V1 Video Projects  Project Id  Videos  Video Id  Segments  Segment Id  Extend Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/video-projects/{project_id}/videos/{video_id}/segments/{segment_id}/inclusion`

Set Segment Inclusion

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "segment_id",
      "required": true,
      "schema": {
        "title": "Segment Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/SegmentInclusionPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Set Segment Inclusion Api V1 Video Projects  Project Id  Videos  Video Id  Segments  Segment Id  Inclusion Put",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/segments/{segment_id}/reassign`

Reassign Segment

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "segment_id",
      "required": true,
      "schema": {
        "title": "Segment Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ReassignPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Reassign Segment Api V1 Video Projects  Project Id  Videos  Video Id  Segments  Segment Id  Reassign Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/segments/{segment_id}/split`

Split Segment

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "segment_id",
      "required": true,
      "schema": {
        "title": "Segment Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/SegmentSplitPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Split Segment Api V1 Video Projects  Project Id  Videos  Video Id  Segments  Segment Id  Split Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/thumbnail`

Video Thumbnail

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {}
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/tracks`

List Tracks

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response List Tracks Api V1 Video Projects  Project Id  Videos  Video Id  Tracks Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/tracks/merge-multiple`

Merge Multiple Tracks

Merge all tracks listed in ``track_ids`` into the first one.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/TrackMergeMultiplePayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Merge Multiple Tracks Api V1 Video Projects  Project Id  Videos  Video Id  Tracks Merge Multiple Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## DELETE `/api/v1/video-projects/{project_id}/videos/{video_id}/tracks/{track_id}`

Delete Track

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "track_id",
      "required": true,
      "schema": {
        "title": "Track Id",
        "type": "integer"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Delete Track Api V1 Video Projects  Project Id  Videos  Video Id  Tracks  Track Id  Delete",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/video-projects/{project_id}/videos/{video_id}/tracks/{track_id}/inclusion`

Set Track Inclusion

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "track_id",
      "required": true,
      "schema": {
        "title": "Track Id",
        "type": "integer"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/InclusionPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Set Track Inclusion Api V1 Video Projects  Project Id  Videos  Video Id  Tracks  Track Id  Inclusion Put",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/tracks/{track_id}/label/{label}`

Label Full Track

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "track_id",
      "required": true,
      "schema": {
        "title": "Track Id",
        "type": "integer"
      }
    },
    {
      "in": "path",
      "name": "label",
      "required": true,
      "schema": {
        "title": "Label",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/RevisionPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Label Full Track Api V1 Video Projects  Project Id  Videos  Video Id  Tracks  Track Id  Label  Label  Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/tracks/{track_id}/merge`

Merge Track

Merge ``source_track_id`` into ``track_id``.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "track_id",
      "required": true,
      "schema": {
        "title": "Track Id",
        "type": "integer"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/TrackMergePayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Merge Track Api V1 Video Projects  Project Id  Videos  Video Id  Tracks  Track Id  Merge Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/tracks/{track_id}/split`

Split Track

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "track_id",
      "required": true,
      "schema": {
        "title": "Track Id",
        "type": "integer"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/TrackSplitPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Split Track Api V1 Video Projects  Project Id  Videos  Video Id  Tracks  Track Id  Split Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/trim`

Trim Video

Persist a frame-accurate trim as either a replacement or a new video.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/VideoTrimPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Trim Video Api V1 Video Projects  Project Id  Videos  Video Id  Trim Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/unapprove`

Unapprove Video

Revoke approval so a video can be re-annotated.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Unapprove Video Api V1 Video Projects  Project Id  Videos  Video Id  Unapprove Post",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/validate`

Validate Video

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Validate Video Api V1 Video Projects  Project Id  Videos  Video Id  Validate Get",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/videos/{video_id}/windows`

List Windows

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "track_id",
      "required": false,
      "schema": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "title": "Track Id"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response List Windows Api V1 Video Projects  Project Id  Videos  Video Id  Windows Get",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## POST `/api/v1/video-projects/{project_id}/videos/{video_id}/windows/generate`

Generate Windows

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Response Generate Windows Api V1 Video Projects  Project Id  Videos  Video Id  Windows Generate Post",
            "type": "array"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/video-projects/{project_id}/videos/{video_id}/windows/{window_id}`

Review Window

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "video_id",
      "required": true,
      "schema": {
        "title": "Video Id",
        "type": "string"
      }
    },
    {
      "in": "path",
      "name": "window_id",
      "required": true,
      "schema": {
        "title": "Window Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/WindowReviewPayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Review Window Api V1 Video Projects  Project Id  Videos  Video Id  Windows  Window Id  Put",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/workspace-changes`

Workspace Changes

Return a compact durable event delta for fallback synchronization.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    },
    {
      "in": "query",
      "name": "after",
      "required": false,
      "schema": {
        "default": 0,
        "minimum": 0,
        "title": "After",
        "type": "integer"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/WorkspaceChangesResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## GET `/api/v1/video-projects/{project_id}/workspace-snapshot`

Workspace Snapshot

Return the one initial state read required to open a workspace.

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/WorkspaceSnapshotResponse"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## PUT `/api/v1/video-projects/{project_id}/workspace-state`

Save Workspace State

```json
{
  "parameters": [
    {
      "in": "path",
      "name": "project_id",
      "required": true,
      "schema": {
        "title": "Project Id",
        "type": "string"
      }
    }
  ],
  "requestBody": {
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/WorkspaceStatePayload"
        }
      }
    },
    "required": true
  },
  "responses": {
    "200": {
      "content": {
        "application/json": {
          "schema": {
            "additionalProperties": true,
            "title": "Response Save Workspace State Api V1 Video Projects  Project Id  Workspace State Put",
            "type": "object"
          }
        }
      },
      "description": "Successful Response"
    },
    "422": {
      "content": {
        "application/json": {
          "schema": {
            "$ref": "#/components/schemas/HTTPValidationError"
          }
        }
      },
      "description": "Validation Error"
    }
  }
}
```

## Shared components

```json
{
  "schemas": {
    "AnnotationDerivativeRefreshResponse": {
      "description": "Result of requesting label-derived windows/features to be rebuilt.",
      "properties": {
        "job": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ProcessingJobResponse"
            },
            {
              "type": "null"
            }
          ]
        },
        "requested_revision": {
          "minimum": 0.0,
          "title": "Requested Revision",
          "type": "integer"
        },
        "status": {
          "enum": [
            "queued",
            "deferred",
            "already_queued"
          ],
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "requested_revision",
        "status"
      ],
      "title": "AnnotationDerivativeRefreshResponse",
      "type": "object"
    },
    "ApprovePayload": {
      "properties": {
        "is_approved": {
          "title": "Is Approved",
          "type": "boolean"
        }
      },
      "required": [
        "is_approved"
      ],
      "title": "ApprovePayload",
      "type": "object"
    },
    "Body_import_model_api_v1_video_projects__project_id__models_import_post": {
      "properties": {
        "artifact": {
          "contentMediaType": "application/octet-stream",
          "title": "Artifact",
          "type": "string"
        },
        "manifest_json": {
          "title": "Manifest Json",
          "type": "string"
        },
        "trusted_local": {
          "default": false,
          "title": "Trusted Local",
          "type": "boolean"
        }
      },
      "required": [
        "artifact",
        "manifest_json"
      ],
      "title": "Body_import_model_api_v1_video_projects__project_id__models_import_post",
      "type": "object"
    },
    "Body_import_videos_api_v1_behavior_inference_videos_post": {
      "properties": {
        "files": {
          "items": {
            "contentMediaType": "application/octet-stream",
            "type": "string"
          },
          "title": "Files",
          "type": "array"
        }
      },
      "required": [
        "files"
      ],
      "title": "Body_import_videos_api_v1_behavior_inference_videos_post",
      "type": "object"
    },
    "Body_import_videos_api_v1_video_projects__project_id__videos_import_post": {
      "properties": {
        "files": {
          "items": {
            "contentMediaType": "application/octet-stream",
            "type": "string"
          },
          "title": "Files",
          "type": "array"
        }
      },
      "required": [
        "files"
      ],
      "title": "Body_import_videos_api_v1_video_projects__project_id__videos_import_post",
      "type": "object"
    },
    "Body_upload_inference_media_api_v1_tasks__task__inference_post": {
      "properties": {
        "files": {
          "items": {
            "contentMediaType": "application/octet-stream",
            "type": "string"
          },
          "title": "Files",
          "type": "array"
        }
      },
      "required": [
        "files"
      ],
      "title": "Body_upload_inference_media_api_v1_tasks__task__inference_post",
      "type": "object"
    },
    "Body_upload_task_images_api_v1_tasks__task__images_upload_post": {
      "properties": {
        "files": {
          "items": {
            "contentMediaType": "application/octet-stream",
            "type": "string"
          },
          "title": "Files",
          "type": "array"
        }
      },
      "required": [
        "files"
      ],
      "title": "Body_upload_task_images_api_v1_tasks__task__images_upload_post",
      "type": "object"
    },
    "BoundingBox": {
      "properties": {
        "class_id": {
          "minimum": 0.0,
          "title": "Class Id",
          "type": "integer"
        },
        "h": {
          "exclusiveMinimum": 0.0,
          "maximum": 1.0,
          "title": "H",
          "type": "number"
        },
        "w": {
          "exclusiveMinimum": 0.0,
          "maximum": 1.0,
          "title": "W",
          "type": "number"
        },
        "x_center": {
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "X Center",
          "type": "number"
        },
        "y_center": {
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Y Center",
          "type": "number"
        }
      },
      "required": [
        "class_id",
        "x_center",
        "y_center",
        "w",
        "h"
      ],
      "title": "BoundingBox",
      "type": "object"
    },
    "HTTPValidationError": {
      "properties": {
        "detail": {
          "items": {
            "$ref": "#/components/schemas/ValidationError"
          },
          "title": "Detail",
          "type": "array"
        }
      },
      "title": "HTTPValidationError",
      "type": "object"
    },
    "ImageItem": {
      "properties": {
        "has_label": {
          "title": "Has Label",
          "type": "boolean"
        },
        "image_url": {
          "title": "Image Url",
          "type": "string"
        },
        "is_approved": {
          "default": false,
          "title": "Is Approved",
          "type": "boolean"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "visualization_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Visualization Url"
        }
      },
      "required": [
        "name",
        "has_label",
        "image_url"
      ],
      "title": "ImageItem",
      "type": "object"
    },
    "InclusionPayload": {
      "properties": {
        "include": {
          "title": "Include",
          "type": "boolean"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Reason"
        }
      },
      "required": [
        "include"
      ],
      "title": "InclusionPayload",
      "type": "object"
    },
    "InferenceMediaItem": {
      "properties": {
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "detections": {
          "title": "Detections",
          "type": "integer"
        },
        "filename": {
          "title": "Filename",
          "type": "string"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "media_type": {
          "title": "Media Type",
          "type": "string"
        },
        "result_url": {
          "title": "Result Url",
          "type": "string"
        },
        "source_url": {
          "title": "Source Url",
          "type": "string"
        },
        "task_id": {
          "title": "Task Id",
          "type": "string"
        }
      },
      "required": [
        "id",
        "task_id",
        "filename",
        "media_type",
        "source_url",
        "result_url",
        "detections",
        "created_at"
      ],
      "title": "InferenceMediaItem",
      "type": "object"
    },
    "JobControl": {
      "properties": {
        "action": {
          "enum": [
            "pause",
            "resume",
            "cancel",
            "retry",
            "prioritize"
          ],
          "title": "Action",
          "type": "string"
        }
      },
      "required": [
        "action"
      ],
      "title": "JobControl",
      "type": "object"
    },
    "LabelPayload": {
      "properties": {
        "boxes": {
          "items": {
            "$ref": "#/components/schemas/BoundingBox"
          },
          "title": "Boxes",
          "type": "array"
        }
      },
      "required": [
        "boxes"
      ],
      "title": "LabelPayload",
      "type": "object"
    },
    "LabelResponse": {
      "properties": {
        "boxes": {
          "items": {
            "$ref": "#/components/schemas/BoundingBox"
          },
          "title": "Boxes",
          "type": "array"
        },
        "filename": {
          "title": "Filename",
          "type": "string"
        }
      },
      "required": [
        "filename",
        "boxes"
      ],
      "title": "LabelResponse",
      "type": "object"
    },
    "OperationResponse": {
      "properties": {
        "message": {
          "title": "Message",
          "type": "string"
        },
        "status": {
          "default": "success",
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "message"
      ],
      "title": "OperationResponse",
      "type": "object"
    },
    "ProcessRequest": {
      "properties": {
        "mode": {
          "enum": [
            "threshold",
            "model"
          ],
          "title": "Mode",
          "type": "string"
        },
        "overwrite_labels": {
          "default": false,
          "title": "Overwrite Labels",
          "type": "boolean"
        },
        "priority": {
          "default": 100,
          "maximum": 10000.0,
          "minimum": 0.0,
          "title": "Priority",
          "type": "integer"
        }
      },
      "required": [
        "mode"
      ],
      "title": "ProcessRequest",
      "type": "object"
    },
    "ProcessingJobResponse": {
      "properties": {
        "error_message": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Error Message"
        },
        "external_model_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "External Model Id"
        },
        "job_id": {
          "title": "Job Id",
          "type": "string"
        },
        "priority": {
          "title": "Priority",
          "type": "integer"
        },
        "progress": {
          "title": "Progress",
          "type": "number"
        },
        "project_id": {
          "title": "Project Id",
          "type": "string"
        },
        "stage": {
          "title": "Stage",
          "type": "string"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "target_mode": {
          "default": "threshold",
          "enum": [
            "threshold",
            "model"
          ],
          "title": "Target Mode",
          "type": "string"
        },
        "video_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Video Id"
        }
      },
      "required": [
        "job_id",
        "project_id",
        "stage",
        "status",
        "priority",
        "progress"
      ],
      "title": "ProcessingJobResponse",
      "type": "object"
    },
    "ProcessingOptionsResponse": {
      "properties": {
        "model_available": {
          "title": "Model Available",
          "type": "boolean"
        },
        "model_message": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Model Message"
        },
        "threshold_available": {
          "title": "Threshold Available",
          "type": "boolean"
        }
      },
      "required": [
        "threshold_available",
        "model_available"
      ],
      "title": "ProcessingOptionsResponse",
      "type": "object"
    },
    "ProjectConfigUpdate": {
      "properties": {
        "config": {
          "additionalProperties": true,
          "title": "Config",
          "type": "object"
        }
      },
      "required": [
        "config"
      ],
      "title": "ProjectConfigUpdate",
      "type": "object"
    },
    "ProjectCreate": {
      "properties": {
        "config": {
          "anyOf": [
            {
              "additionalProperties": true,
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "title": "Config"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        }
      },
      "required": [
        "name"
      ],
      "title": "ProjectCreate",
      "type": "object"
    },
    "QueueRequest": {
      "properties": {
        "priority": {
          "default": 100,
          "maximum": 10000.0,
          "minimum": 0.0,
          "title": "Priority",
          "type": "integer"
        }
      },
      "title": "QueueRequest",
      "type": "object"
    },
    "ReassignPayload": {
      "properties": {
        "expected_revision": {
          "minimum": 0.0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "target_track_id": {
          "minimum": 0.0,
          "title": "Target Track Id",
          "type": "integer"
        }
      },
      "required": [
        "expected_revision",
        "target_track_id"
      ],
      "title": "ReassignPayload",
      "type": "object"
    },
    "RevisionPayload": {
      "properties": {
        "expected_revision": {
          "minimum": 0.0,
          "title": "Expected Revision",
          "type": "integer"
        }
      },
      "required": [
        "expected_revision"
      ],
      "title": "RevisionPayload",
      "type": "object"
    },
    "SegmentInclusionPayload": {
      "properties": {
        "expected_revision": {
          "minimum": 0.0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "include": {
          "title": "Include",
          "type": "boolean"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Reason"
        }
      },
      "required": [
        "include",
        "expected_revision"
      ],
      "title": "SegmentInclusionPayload",
      "type": "object"
    },
    "SegmentMergePayload": {
      "properties": {
        "expected_revision": {
          "minimum": 0.0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "segment_ids": {
          "items": {
            "type": "string"
          },
          "minItems": 2,
          "title": "Segment Ids",
          "type": "array"
        }
      },
      "required": [
        "expected_revision",
        "segment_ids"
      ],
      "title": "SegmentMergePayload",
      "type": "object"
    },
    "SegmentSplitPayload": {
      "properties": {
        "expected_revision": {
          "minimum": 0.0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "frame": {
          "minimum": 0.0,
          "title": "Frame",
          "type": "integer"
        }
      },
      "required": [
        "expected_revision",
        "frame"
      ],
      "title": "SegmentSplitPayload",
      "type": "object"
    },
    "SegmentWrite": {
      "properties": {
        "end_frame": {
          "minimum": 0.0,
          "title": "End Frame",
          "type": "integer"
        },
        "expected_revision": {
          "minimum": 0.0,
          "title": "Expected Revision",
          "type": "integer"
        },
        "label": {
          "enum": [
            "others",
            "running",
            "falling"
          ],
          "title": "Label",
          "type": "string"
        },
        "start_frame": {
          "minimum": 0.0,
          "title": "Start Frame",
          "type": "integer"
        },
        "track_id": {
          "minimum": 0.0,
          "title": "Track Id",
          "type": "integer"
        }
      },
      "required": [
        "track_id",
        "start_frame",
        "end_frame",
        "label",
        "expected_revision"
      ],
      "title": "SegmentWrite",
      "type": "object"
    },
    "TaskInfo": {
      "properties": {
        "class_names": {
          "additionalProperties": {
            "type": "string"
          },
          "title": "Class Names",
          "type": "object"
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "temporary_class_id": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Temporary Class Id"
        }
      },
      "required": [
        "id",
        "name",
        "class_names"
      ],
      "title": "TaskInfo",
      "type": "object"
    },
    "ThresholdProfilePayload": {
      "properties": {
        "config": {
          "additionalProperties": true,
          "title": "Config",
          "type": "object"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "profile_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Profile Id"
        }
      },
      "required": [
        "name",
        "config"
      ],
      "title": "ThresholdProfilePayload",
      "type": "object"
    },
    "TrackMergeMultiplePayload": {
      "description": "Payload for merging multiple tracks into the first one in the list.",
      "properties": {
        "track_ids": {
          "items": {
            "type": "integer"
          },
          "minItems": 2,
          "title": "Track Ids",
          "type": "array"
        }
      },
      "required": [
        "track_ids"
      ],
      "title": "TrackMergeMultiplePayload",
      "type": "object"
    },
    "TrackMergePayload": {
      "properties": {
        "source_track_id": {
          "minimum": 0.0,
          "title": "Source Track Id",
          "type": "integer"
        }
      },
      "required": [
        "source_track_id"
      ],
      "title": "TrackMergePayload",
      "type": "object"
    },
    "TrackSplitPayload": {
      "properties": {
        "frame": {
          "minimum": 0.0,
          "title": "Frame",
          "type": "integer"
        }
      },
      "required": [
        "frame"
      ],
      "title": "TrackSplitPayload",
      "type": "object"
    },
    "ValidationError": {
      "properties": {
        "ctx": {
          "title": "Context",
          "type": "object"
        },
        "input": {
          "title": "Input"
        },
        "loc": {
          "items": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "integer"
              }
            ]
          },
          "title": "Location",
          "type": "array"
        },
        "msg": {
          "title": "Message",
          "type": "string"
        },
        "type": {
          "title": "Error Type",
          "type": "string"
        }
      },
      "required": [
        "loc",
        "msg",
        "type"
      ],
      "title": "ValidationError",
      "type": "object"
    },
    "VideoDeleteResponse": {
      "properties": {
        "deleted": {
          "title": "Deleted",
          "type": "boolean"
        },
        "filename": {
          "title": "Filename",
          "type": "string"
        },
        "owned_copy_removed": {
          "title": "Owned Copy Removed",
          "type": "boolean"
        },
        "video_id": {
          "title": "Video Id",
          "type": "string"
        }
      },
      "required": [
        "video_id",
        "filename",
        "deleted",
        "owned_copy_removed"
      ],
      "title": "VideoDeleteResponse",
      "type": "object"
    },
    "VideoRenamePayload": {
      "description": "User-selected basename used for a project-wide video rename.",
      "properties": {
        "prefix": {
          "maxLength": 80,
          "minLength": 1,
          "title": "Prefix",
          "type": "string"
        }
      },
      "required": [
        "prefix"
      ],
      "title": "VideoRenamePayload",
      "type": "object"
    },
    "VideoTrimPayload": {
      "description": "Inclusive canonical-frame range and destination for a video trim.",
      "properties": {
        "end_frame": {
          "minimum": 0.0,
          "title": "End Frame",
          "type": "integer"
        },
        "filename": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Filename"
        },
        "save_mode": {
          "enum": [
            "replace",
            "copy"
          ],
          "title": "Save Mode",
          "type": "string"
        },
        "start_frame": {
          "minimum": 0.0,
          "title": "Start Frame",
          "type": "integer"
        },
        "suggestion_mode": {
          "default": "threshold",
          "enum": [
            "threshold",
            "model"
          ],
          "title": "Suggestion Mode",
          "type": "string"
        }
      },
      "required": [
        "start_frame",
        "end_frame",
        "save_mode"
      ],
      "title": "VideoTrimPayload",
      "type": "object"
    },
    "WindowReviewPayload": {
      "properties": {
        "include": {
          "title": "Include",
          "type": "boolean"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Reason"
        }
      },
      "required": [
        "include"
      ],
      "title": "WindowReviewPayload",
      "type": "object"
    },
    "WorkspaceChangesResponse": {
      "description": "A bounded cursor-based event delta for workspace reconnection.",
      "properties": {
        "events": {
          "items": {
            "$ref": "#/components/schemas/WorkspaceEventResponse"
          },
          "title": "Events",
          "type": "array"
        },
        "has_more": {
          "default": false,
          "title": "Has More",
          "type": "boolean"
        },
        "last_event_id": {
          "minimum": 0.0,
          "title": "Last Event Id",
          "type": "integer"
        },
        "resync_required": {
          "default": false,
          "title": "Resync Required",
          "type": "boolean"
        }
      },
      "required": [
        "events",
        "last_event_id"
      ],
      "title": "WorkspaceChangesResponse",
      "type": "object"
    },
    "WorkspaceEventResponse": {
      "description": "One durable workspace event delivered by delta polling or SSE.",
      "properties": {
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "event_id": {
          "minimum": 1.0,
          "title": "Event Id",
          "type": "integer"
        },
        "event_type": {
          "title": "Event Type",
          "type": "string"
        },
        "payload": {
          "additionalProperties": true,
          "title": "Payload",
          "type": "object"
        },
        "project_id": {
          "title": "Project Id",
          "type": "string"
        },
        "video_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Video Id"
        }
      },
      "required": [
        "event_id",
        "project_id",
        "event_type",
        "payload",
        "created_at"
      ],
      "title": "WorkspaceEventResponse",
      "type": "object"
    },
    "WorkspaceSnapshotResponse": {
      "description": "The initial compact state read for one video-labeling workspace.",
      "properties": {
        "exports": {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Exports",
          "type": "array"
        },
        "jobs": {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Jobs",
          "type": "array"
        },
        "last_event_id": {
          "minimum": 0.0,
          "title": "Last Event Id",
          "type": "integer"
        },
        "processing_options": {
          "$ref": "#/components/schemas/ProcessingOptionsResponse"
        },
        "project": {
          "additionalProperties": true,
          "title": "Project",
          "type": "object"
        },
        "videos": {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Videos",
          "type": "array"
        }
      },
      "required": [
        "project",
        "videos",
        "jobs",
        "processing_options",
        "last_event_id"
      ],
      "title": "WorkspaceSnapshotResponse",
      "type": "object"
    },
    "WorkspaceStatePayload": {
      "properties": {
        "frame_index": {
          "default": 0,
          "minimum": 0.0,
          "title": "Frame Index",
          "type": "integer"
        },
        "suggestion_source": {
          "default": "Threshold",
          "enum": [
            "Off",
            "Threshold",
            "AI"
          ],
          "title": "Suggestion Source",
          "type": "string"
        },
        "track_id": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "title": "Track Id"
        },
        "video_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Video Id"
        }
      },
      "title": "WorkspaceStatePayload",
      "type": "object"
    }
  }
}
```
<!-- END GENERATED -->
