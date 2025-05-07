/* eslint-disable @typescript-eslint/no-empty-object-type */
"use client";

import * as React from "react";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className = "", ...props }, ref) => {
    const baseClasses =
      "block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm " +
      "shadow-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none " +
      "focus:ring-2 focus:ring-blue-400";

    return (
      <textarea
        ref={ref}
        className={`${baseClasses} ${className}`}
        {...props}
      />
    );
  }
);

Textarea.displayName = "Textarea";
