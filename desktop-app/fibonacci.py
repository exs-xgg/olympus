def fibonacci_series(n):
    series = [0, 1]
    while len(series) < n:
        series.append(series[-1] + series[-2])
    return series

if __name__ == "__main__":
    fib_series = fibonacci_series(100)
    print(fib_series)