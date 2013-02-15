
def func2(arg):
    print arg
    return arg + 5

def main():
    x = 5
    x += 6
    val = func2(x)
    print x, val

if __name__ == '__main__':
    main()
