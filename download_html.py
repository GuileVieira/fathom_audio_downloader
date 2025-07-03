#!/usr/bin/env python3
"""
Script para baixar HTML das páginas do Fathom

Uso:
    python download_html.py

Este script usa a mesma infraestrutura do fathom_batch_processor.py
mas foca apenas no download do HTML das páginas.
"""

import asyncio
from fathom_batch_processor import FathomBatchProcessor

async def main():
    """Função principal para baixar HTML"""
    print("🌐 FATHOM HTML DOWNLOADER")
    print("=" * 50)
    
    processor = FathomBatchProcessor()
    await processor.download_html_pages()
    
    print("\n🎉 Download de HTML concluído!")

if __name__ == '__main__':
    asyncio.run(main()) 