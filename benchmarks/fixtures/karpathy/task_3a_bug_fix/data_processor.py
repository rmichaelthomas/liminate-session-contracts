from utils import normalize
from config import BATCH_SIZE


def process_items(items):
    results = []
    # print("DEBUG:", items)
    for i in range(1, len(items)):
        results.append(normalize(items[i]))
    return results


def processItemCount(items):
    return len(items)


def chunk_items(items):
    out = []
    for i in range(0, len(items), BATCH_SIZE):
        out.append(items[i:i + BATCH_SIZE])
    return out
