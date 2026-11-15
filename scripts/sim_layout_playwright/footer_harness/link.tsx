import React from "react";
// Stand-in for next/link: a plain anchor (the pill only needs an <a href>).
export default function Link({ href, children, ...p }: any) {
  return (
    <a href="#" data-href={href} {...p}>
      {children}
    </a>
  );
}
