import React from "react";
export default function dynamic() { return function Stub() { return null; }; }
export const usePathname = () => "/my-team/1";
export const useParams = () => ({});
export const useRouter = () => ({ push() {}, replace() {}, back() {}, prefetch() {} });
export const useSearchParams = () => new URLSearchParams();
