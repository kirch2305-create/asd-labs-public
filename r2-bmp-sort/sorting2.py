import sys
import struct
import time

def read_bmp(filename):
    try:
        with open(filename, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"Ошибка: не удалось открыть файл {filename} ({e})", file=sys.stderr)
        return [], 0, 0

    if len(data) < 54:
        print("Ошибка: файл слишком мал для BMP.", file=sys.stderr)
        return [], 0, 0
    if data[0:2] != b'BM':
        print("Ошибка: файл не является BMP (неверная сигнатура).", file=sys.stderr)
        return [], 0, 0

    bfOffBits = struct.unpack('<I', data[10:14])[0]
    biWidth = struct.unpack('<i', data[18:22])[0]
    biHeight = struct.unpack('<i', data[22:26])[0]
    biBitCount = struct.unpack('<H', data[28:30])[0]
    biCompression = struct.unpack('<I', data[30:34])[0]

    if biBitCount != 24 or biCompression != 0:
        print("Ошибка: поддерживается только 24-битный несжатый BMP.", file=sys.stderr)
        return [], 0, 0

    width = abs(biWidth)
    height = abs(biHeight)
    row_size = (width * 3 + 3) & ~3
    padding = row_size - (width * 3)

    pixels = []
    offset = bfOffBits
    for y in range(height):
        for x in range(width):
            if offset + 3 > len(data):
                print("Ошибка: BMP файл усечен (не хватает пикселей).", file=sys.stderr)
                return [], 0, 0
            pixels.append(data[offset:offset + 3])
            offset += 3
        offset += padding

    return pixels, width, height

def read_keys(filename):
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Ошибка: не удалось открыть файл {filename} ({e})", file=sys.stderr)
        return []

    if not lines:
        print("Ошибка: файл ключей пуст.", file=sys.stderr)
        return []

    try:
        n = int(lines[0].strip())
        if len(lines) - 1 < n:
            print("Ошибка: в файле ключей меньше чисел, чем заявлено.", file=sys.stderr)
            return []
        keys = [int(x.strip()) for x in lines[1:n + 1]]
        return keys
    except ValueError:
        print("Ошибка: файл ключей содержит нечисловые данные.", file=sys.stderr)
        return []

def write_bmp(filename, pixels, width, height):
    row_size = (width * 3 + 3) & ~3
    padding = row_size - (width * 3)
    image_size = row_size * height
    file_size = 54 + image_size

    try:
        with open(filename, "wb") as f:
            f.write(b'BM')
            f.write(struct.pack('<I', file_size))
            f.write(struct.pack('<I', 0))
            f.write(struct.pack('<I', 54))
            f.write(struct.pack('<I', 40))
            f.write(struct.pack('<i', width))
            f.write(struct.pack('<i', height))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', 24))
            f.write(struct.pack('<I', 0))
            f.write(struct.pack('<I', image_size))
            f.write(struct.pack('<i', 2835))
            f.write(struct.pack('<i', 2835))
            f.write(struct.pack('<I', 0))
            f.write(struct.pack('<I', 0))

            pad_bytes = b'\x00' * padding
            idx = 0
            for y in range(height):
                for x in range(width):
                    f.write(pixels[idx])
                    idx += 1
                if padding > 0:
                    f.write(pad_bytes)
    except Exception as e:
        print(f"Ошибка при записи файла {filename}: {e}", file=sys.stderr)

def _sift_down(items, n, i):
    while True:
        largest = i
        left = 2 * i + 1
        right = 2 * i + 2

        if left < n and items[left] > items[largest]:
            largest = left
        if right < n and items[right] > items[largest]:
            largest = right

        if largest == i:
            break

        items[i], items[largest] = items[largest], items[i]
        i = largest

def stable_heap_sort(keys, pixels):
    n = len(keys)
    items = [(keys[i], i, pixels[i]) for i in range(n)]

    for i in range(n // 2 - 1, -1, -1):
        _sift_down(items, n, i)

    for i in range(n - 1, 0, -1):
        items[0], items[i] = items[i], items[0]
        _sift_down(items, i, 0)

    for i in range(n):
        pixels[i] = items[i][2]

def main():
    args = sys.argv[1:]
    bmp_path = keys_path = out_path = None
    bench_reps = 0

    i = 0
    while i < len(args):
        if args[i] == "--bmp" and i + 1 < len(args):
            bmp_path = args[i + 1]
            i += 2
        elif args[i] == "--keys" and i + 1 < len(args):
            keys_path = args[i + 1]
            i += 2
        elif args[i] == "--out" and i + 1 < len(args):
            out_path = args[i + 1]
            i += 2
        elif args[i] == "--bench" and i + 1 < len(args):
            try:
                bench_reps = int(args[i + 1])
            except ValueError:
                bench_reps = 0
            i += 2
        else:
            i += 1

    if not bmp_path or not keys_path or not out_path:
        print("Использование: restore --bmp <in.bmp> --keys <keys.txt> --out <out.bmp> [--bench N]", file=sys.stderr)
        sys.exit(1)

    pixels, width, height = read_bmp(bmp_path)
    if not pixels:
        sys.exit(1)

    keys = read_keys(keys_path)
    if not keys:
        sys.exit(1)

    if len(keys) != len(pixels):
        print("Ошибка: количество ключей не совпадает с количеством пикселей.", file=sys.stderr)
        sys.exit(1)

    if bench_reps > 0:
        times = []
        for _ in range(bench_reps):
            k_copy = keys.copy()
            p_copy = pixels.copy()

            start_time = time.perf_counter()
            stable_heap_sort(k_copy, p_copy)
            end_time = time.perf_counter()

            times.append((end_time - start_time) * 1000)

        times.sort()
        median_time = times[len(times) // 2]
        print(f"Время сортировки (медиана из {bench_reps}): {median_time:.3f} мс")

        stable_heap_sort(keys, pixels)
    else:
        stable_heap_sort(keys, pixels)

    write_bmp(out_path, pixels, width, height)
    print("Программа успешно завершила работу.")

if __name__ == "__main__":
    main()