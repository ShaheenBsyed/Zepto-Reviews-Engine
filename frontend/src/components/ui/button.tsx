import * as React from "react";

import { cn } from "@/lib/utils";

function Button({ className, variant = "default", size = "default", ...props }: React.ComponentProps<"button"> & { variant?: "default" | "ghost" | "outline"; size?: "default" | "icon" | "sm" | "lg" }) {
  const variants = {
    default: "bg-primary text-white hover:bg-primary/90 shadow-sm",
    ghost: "hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300",
    outline: "border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900",
  };

  const sizes = {
    default: "h-10 px-4 py-2",
    sm: "h-8 px-3 text-xs",
    lg: "h-12 px-6 text-base",
    icon: "h-10 w-10",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}

export { Button };
