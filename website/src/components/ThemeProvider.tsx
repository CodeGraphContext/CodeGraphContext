"use client"

import * as React from "react"
import { ThemeProvider as NextThemesProvider } from "next-themes"
import { type ThemeProviderProps } from "next-themes/dist/types"

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  const storedTheme =
    typeof window !== "undefined" ? window.localStorage.getItem("theme") : null
  const defaultTheme =
    storedTheme === "light" || storedTheme === "dark"
      ? storedTheme
      : props.defaultTheme

  return (
    <NextThemesProvider {...props} defaultTheme={defaultTheme}>
      {children}
    </NextThemesProvider>
  )
}
