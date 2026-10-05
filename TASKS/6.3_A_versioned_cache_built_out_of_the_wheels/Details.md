# 6.3 A versioned cache built out of the wheels

Built.  Left over, from 6.3.11: two separate `install` calls asking for
different versions of one package are not caught, and the second
silently gets the first version.
