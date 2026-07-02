#ifndef WIN_COMPAT_H_INCLUDED
#define WIN_COMPAT_H_INCLUDED

// Windows/MinGW portability shims for POSIX facilities this Linux-built fork uses.
// The Windows CRT has no flockfile/funlockfile; map them to its stream-lock API.
#if defined(_WIN32)
    #include <cstdio>
    #define flockfile(stream)   _lock_file(stream)
    #define funlockfile(stream) _unlock_file(stream)
#endif

#endif // WIN_COMPAT_H_INCLUDED
