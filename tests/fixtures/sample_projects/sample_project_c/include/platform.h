#ifndef PLATFORM_H
#define PLATFORM_H

#if defined(_WIN32) || defined(_WIN64)
  #define CGC_PLATFORM_WINDOWS 1
#else
  #define CGC_PLATFORM_POSIX 1
#endif

#endif
