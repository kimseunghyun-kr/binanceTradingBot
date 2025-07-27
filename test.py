# test_celery_imports.py
import os
import sys

print("CWD:", os.getcwd())
print("sys.path[0]:", sys.path[0])
print("sys.path:", sys.path)

try:
    from strategyOrchestrator import entities

    print("✅ import entities: OK")
except Exception as e:
    print("❌ import entities:", e)

try:
    import strategyOrchestrator.entities.strategies.BaseStrategy
    print("✅ import entities.strategies.BaseStrategy: OK")
except Exception as e:
    print("❌ import entities.strategies.BaseStrategy:", e)
