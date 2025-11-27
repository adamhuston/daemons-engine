For the backend, we need a database layer, a game engine, and an API layer.

Recommended backend architecture from ChatGPT:

```
 app/
    __init__.py
    main.py          # FastAPI app, WS endpoints, startup/shutdown hooks
    db.py            # engine, session factory
    models.py        # SQLAlchemy models (Room, Player, Item, etc.)
    schemas.py       # Pydantic models for messages
    engine/
      __init__.py
      world.py       # dataclasses for Room, Player, Item in memory
      engine.py      # WorldEngine: game loop, command handling
```

