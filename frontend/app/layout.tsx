import type { ReactNode } from 'react';
export const metadata = { title: 'AI Chatbot Builder', description: 'Multi-tenant AI chatbot builder with advanced RAG' };
export default function RootLayout({ children }: { children: ReactNode }) { return <html lang="en"><body style={{margin:0,fontFamily:'Inter,system-ui,sans-serif',background:'#f8fafc',color:'#172033'}}>{children}</body></html>; }
