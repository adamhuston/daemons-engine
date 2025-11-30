After reviewing the protocol documentation against the CMS roadmap, here are the **critical gaps** that need to be filled:

## 🚨 Critical Missing Endpoints

### **1. Schema Registry API** (Phase 1 Blocker)
**Required for:** Schema system foundation - the entire CMS architecture depends on this

````python
# MISSING - High Priority
@router.get("/api/admin/schemas")
async def get_schemas(
    include_version: bool = True,
    schema_type: Optional[str] = None  # "rooms", "items", "npcs", etc.
):
    """
    Return all _schema.yaml files with metadata.

    Response:
    {
      "version": "1.0.0",
      "schemas": {
        "rooms": {
          "content": "... yaml content ...",
          "last_modified": 1638360000.0,
          "checksum": "sha256_hash"
        },
        "items": {...},
        "npcs": {...}
      }
    }
    """
````

**Why Critical:** Phase 1 requires fetching schemas from server. Without this, the CMS can't generate TypeScript types or validators.

---

### **2. YAML File Upload/Update** (Phase 2B-5A Gap)
**Required for:** CMS → Server content push workflow

````python
# MISSING - High Priority
@router.post("/api/admin/content/upload")
async def upload_content(
    content_type: str,  # "rooms", "items", etc.
    file_path: str,     # Relative to world_data/
    content: str,       # YAML content
    validate_only: bool = False
):
    """
    Upload/update a YAML file.
    If validate_only=True, don't write to disk.

    Response:
    {
      "success": true,
      "validation_errors": [],
      "file_written": "/path/to/world_data/rooms/custom/room.yaml",
      "auto_reload_triggered": true
    }
    """
````

**Why Critical:** Current `/api/admin/content/reload` only reloads *existing* files. CMS needs to create/update YAML files from the UI.

---

### **3. File Listing/Directory Structure** (Phase 2A Gap)
**Required for:** File tree explorer

````python
# MISSING - Medium Priority
@router.get("/api/admin/content/files")
async def list_content_files(
    content_type: Optional[str] = None,
    include_git_status: bool = False
):
    """
    List all YAML files in world_data/.

    Response:
    {
      "files": [
        {
          "path": "rooms/ethereal/room_1_1_1.yaml",
          "content_type": "rooms",
          "size_bytes": 1024,
          "last_modified": 1638360000.0,
          "git_status": "modified"  # if include_git_status=True
        }
      ]
    }
    """
````

**Why Important:** CMS file tree needs to show existing content. Alternative is to read local git clone directly, but server endpoint is cleaner.

---

### **4. YAML File Download** (Phase 2A Gap)
**Required for:** Editing existing content

````python
# MISSING - High Priority
@router.get("/api/admin/content/download")
async def download_content(
    file_path: str  # Relative to world_data/
):
    """
    Download raw YAML content.

    Response:
    {
      "content": "id: room_1_1_1\nname: Central Chamber\n...",
      "checksum": "sha256_hash",
      "last_modified": 1638360000.0
    }
    """
````

**Why Critical:** CMS needs to fetch existing YAML to edit it.

---

### **5. Reference Validation** (Phase 2A Gap)
**Required for:** Detecting broken links between content

````python
# MISSING - Medium Priority
@router.post("/api/admin/content/validate-references")
async def validate_references(
    content: str,       # YAML content to validate
    content_type: str   # "rooms", "items", etc.
):
    """
    Validate that all references (room exits, item templates, NPC spawns)
    point to existing content.

    Response:
    {
      "valid": false,
      "broken_references": [
        {
          "field": "exits.north",
          "referenced_id": "room_99_99_99",
          "error": "Room does not exist"
        }
      ]
    }
    """
````

**Why Important:** Real-time validation in Monaco editor needs this. Could be done client-side with cached data, but server is authoritative.

---

### **6. Git Operations via API** (Phase 2B Gap)
**Required for:** Server-side git commit/push

````python
# MISSING - Low Priority (CMS can use local git)
@router.post("/api/admin/git/commit")
async def git_commit(
    message: str,
    files: List[str]  # Relative paths to world_data/
):
    """
    Commit specified files to server's git repo.
    Optional - CMS can manage git locally instead.
    """
````

**Why Low Priority:** Design doc says "git as source of truth" but doesn't specify *where* git lives. If CMS manages local clone, this isn't needed.

---

## 📋 Minor Enhancements Needed

### **7. Enhanced `/api/admin/content/validate`**
Current implementation validates syntax only. Needs:

````python
# ENHANCE EXISTING
@router.post("/api/admin/content/validate")
async def validate_content(
    content_type: str,
    content: str,  # ADD: Accept raw YAML string, not just file_path
    file_path: Optional[str] = None,
    check_references: bool = True  # ADD: Enable reference checking
):
    """
    Validate YAML content before saving.
    """
````

---

### **8. Schema Version Endpoint**
**Required for:** Schema version detection (Phase 1)

````python
# MISSING - Low Priority
@router.get("/api/admin/schemas/version")
async def get_schema_version():
    """
    Return current schema version.

    Response:
    {
      "version": "1.0.0",
      "engine_version": "0.9.0",
      "last_modified": 1638360000.0
    }
    """
````

**Why Useful:** CMS can detect when server schemas are newer than cached version.

---

### **9. Bulk Operations**
**Required for:** Phase 4B bulk import/export

````python
# MISSING - Low Priority
@router.post("/api/admin/content/bulk-import")
async def bulk_import(
    content_type: str,
    items: List[dict]  # CSV → dict conversion done client-side
):
    """
    Import multiple items at once (e.g., 100 item templates from CSV).
    """
````

---

## 🎯 Priority Breakdown

### **Must Have for Phase 1:**
1. ✅ GET `/api/admin/schemas` - Schema Registry API
2. ✅ POST `/api/admin/content/upload` - YAML file upload
3. ✅ GET `/api/admin/content/download` - YAML file download

### **Must Have for Phase 2:**
4. ✅ GET `/api/admin/content/files` - File listing
5. ✅ Enhanced `/api/admin/content/validate` - Accept raw YAML

### **Nice to Have:**
6. ⚠️ POST `/api/admin/content/validate-references` - Reference checking
7. ⚠️ GET `/api/admin/schemas/version` - Version detection
8. ⚠️ POST `/api/admin/git/*` - Git operations (optional)

---

## 🔧 Alternative: Hybrid Approach

If server endpoints are slow to implement, the CMS could:

1. **Read** from local git clone (file tree, YAML content)
2. **Validate** using local schema cache + Zod
3. **Write** to local YAML files
4. **Sync** to server via git push
5. **Trigger hot-reload** via existing `/api/admin/content/reload`

**Trade-off:** This requires CMS to manage a full git clone and handle git operations directly. Server API approach is cleaner but requires more server work.

---

## Recommendation

**Phase 1 Server Work (Critical Path):**
```python
# Add these 3 endpoints to unblock CMS development:
1. GET  /api/admin/schemas
2. POST /api/admin/content/upload
3. GET  /api/admin/content/download
```

**Phase 2 Server Work:**
```python
4. GET  /api/admin/content/files
5. POST /api/admin/content/validate (enhanced)
```

Everything else can be deferred or handled client-side.
