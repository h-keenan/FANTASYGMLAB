import React from "react";
// Stand-ins for next/image and next/navigation (the footer harness mounts the real SimGameOrb, Sheet and OverlayRuntime).
export default function Image({ src, alt, width, height, className, style }: any) {
  return <img src={typeof src === "string" ? src : src?.src} alt={alt} width={width} height={height} className={className} style={style} />;
}
export const usePathname = () => "/my-team/1";
export const useRouter = () => ({ push() {}, replace() {}, back() {}, prefetch() {} });
