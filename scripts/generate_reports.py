#!/usr/bin/env python3
"""
Script para gerar relatórios e analytics dos dados do Fathom
"""

import sys
import os
from pathlib import Path
import json
import argparse
from datetime import datetime, date
from typing import Dict, Any, List
import webbrowser

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database_manager import DatabaseManager
from config import Config
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FathomReportsGenerator:
    """Gerador de relatórios para dados do Fathom"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
    
    def generate_console_report(self) -> bool:
        """Gera relatório rápido no console"""
        
        print("📊 FATHOM ANALYTICS - RELATÓRIO GERAL")
        print("=" * 60)
        
        if not self.db_manager.connected:
            print("❌ Não conectado ao banco de dados")
            return False
        
        try:
            # Busca dados analytics
            analytics = self.db_manager.get_analytics_data()
            
            if 'error' in analytics:
                print(f"❌ Erro ao buscar dados: {analytics['error']}")
                return False
            
            # Estatísticas gerais
            print("\n📈 ESTATÍSTICAS GERAIS:")
            print("-" * 30)
            print(f"📞 Total de Chamadas: {analytics['total_calls']}")
            
            if analytics.get('summary_stats'):
                stats = analytics['summary_stats']
                print(f"⏱️  Duração Total: {stats.get('total_duration_minutes', 0)} minutos")
                print(f"📊 Duração Média: {stats.get('avg_duration_minutes', 0):.1f} minutos")
                print(f"👥 Participantes Únicos: {stats.get('unique_participants', 0)}")
                print(f"🏢 Empresas Únicas: {stats.get('unique_companies', 0)}")
                print(f"🎤 Hosts Únicos: {stats.get('unique_hosts', 0)}")
            
            # Top Hosts
            print("\n🏆 TOP HOSTS:")
            print("-" * 30)
            host_stats = analytics.get('by_host', {})
            sorted_hosts = sorted(host_stats.items(), key=lambda x: x[1]['call_count'], reverse=True)
            
            for i, (host, stats) in enumerate(sorted_hosts[:5], 1):
                print(f"{i}. {host}")
                print(f"   📞 Chamadas: {stats['call_count']}")
                print(f"   ⏱️  Duração Total: {stats['total_duration']:.0f} min")
            
            print("\n✅ Relatório gerado com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao gerar relatório: {e}")
            return False
    
    def generate_html_report(self) -> bool:
        """Gera relatório HTML completo"""
        
        print("🌐 Gerando relatório HTML...")
        
        if not self.db_manager.connected:
            print("❌ Não conectado ao banco de dados")
            return False
        
        try:
            # Busca dados
            analytics = self.db_manager.get_analytics_data()
            
            if 'error' in analytics:
                print(f"❌ Erro ao buscar dados: {analytics['error']}")
                return False
            
            # Gera HTML
            html_content = self._generate_html_content(analytics)
            
            # Salva arquivo
            html_file = self.reports_dir / f"fathom_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ Relatório HTML salvo: {html_file}")
            
            # Pergunta se quer abrir
            response = input("🌐 Deseja abrir o relatório no navegador? (s/n): ").lower().strip()
            if response in ['s', 'sim', 'y', 'yes']:
                webbrowser.open(f"file://{html_file.absolute()}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao gerar relatório HTML: {e}")
            return False
    
    def generate_json_report(self) -> bool:
        """Gera relatório em formato JSON"""
        
        print("📄 Gerando relatório JSON...")
        
        if not self.db_manager.connected:
            print("❌ Não conectado ao banco de dados")
            return False
        
        try:
            # Busca dados
            analytics = self.db_manager.get_analytics_data()
            
            if 'error' in analytics:
                print(f"❌ Erro ao buscar dados: {analytics['error']}")
                return False
            
            # Salva JSON
            json_file = self.reports_dir / f"fathom_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(analytics, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"✅ Relatório JSON salvo: {json_file}")
            print(f"📊 Total de dados: {len(str(analytics))} caracteres")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao gerar relatório JSON: {e}")
            return False
    
    def _generate_html_content(self, analytics: Dict[str, Any]) -> str:
        """Gera conteúdo HTML do relatório"""
        
        # Prepara dados para gráficos
        monthly_data = analytics.get('by_month', {})
        host_data = analytics.get('by_host', {})
        topics_data = analytics.get('topics_analysis', {})
        duration_data = analytics.get('duration_analysis', {})
        
        # Dados para gráfico mensal
        months = sorted(monthly_data.keys())
        monthly_calls = [monthly_data[m]['call_count'] for m in months]
        monthly_duration = [monthly_data[m]['total_duration'] for m in months]
        
        # Top 10 hosts
        top_hosts = sorted(host_data.items(), key=lambda x: x[1]['call_count'], reverse=True)[:10]
        host_names = [h[0] for h in top_hosts]
        host_calls = [h[1]['call_count'] for h in top_hosts]
        
        # Top 10 tópicos
        top_topics = sorted(topics_data.items(), key=lambda x: x[1]['frequency'], reverse=True)[:10]
        topic_names = [t[0] for t in top_topics]
        topic_freq = [t[1]['frequency'] for t in top_topics]
        
        # Distribuição de duração
        dist = duration_data.get('distribution', {})
        duration_labels = ['Curtas (< 10min)', 'Médias (10-30min)', 'Longas (> 30min)']
        duration_values = [dist.get('short_calls', 0), dist.get('medium_calls', 0), dist.get('long_calls', 0)]
        
        html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fathom Analytics - Relatório</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-top: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 20px 0;
        }}
        .table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .table th, .table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .table th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .table tr:hover {{
            background-color: #f5f5f5;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Fathom Analytics - Relatório Completo</h1>
        <p style="text-align: center; color: #666;">
            Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
        </p>
        
        <h2>📈 Estatísticas Gerais</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{analytics['total_calls']}</div>
                <div class="stat-label">Total de Chamadas</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{analytics.get('summary_stats', {}).get('total_duration_minutes', 0)}</div>
                <div class="stat-label">Minutos Totais</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{analytics.get('summary_stats', {}).get('unique_participants', 0)}</div>
                <div class="stat-label">Participantes Únicos</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{analytics.get('summary_stats', {}).get('unique_hosts', 0)}</div>
                <div class="stat-label">Hosts Únicos</div>
            </div>
        </div>
        
        <h2>📅 Atividade por Mês</h2>
        <div class="chart-container">
            <canvas id="monthlyChart"></canvas>
        </div>
        
        <h2>🏆 Top Hosts</h2>
        <div class="chart-container">
            <canvas id="hostsChart"></canvas>
        </div>
        
        <h2>🎯 Tópicos Mais Discutidos</h2>
        <div class="chart-container">
            <canvas id="topicsChart"></canvas>
        </div>
        
        <h2>⏱️ Distribuição de Duração</h2>
        <div class="chart-container">
            <canvas id="durationChart"></canvas>
        </div>
        
        <h2>📋 Detalhes dos Hosts</h2>
        <table class="table">
            <thead>
                <tr>
                    <th>Host</th>
                    <th>Chamadas</th>
                    <th>Duração Total (min)</th>
                    <th>Duração Média (min)</th>
                    <th>Participantes Médios</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f'<tr><td>{host}</td><td>{stats["call_count"]}</td><td>{stats["total_duration"]:.0f}</td><td>{stats.get("avg_duration", 0):.1f}</td><td>{stats.get("avg_participants", 0):.1f}</td></tr>' for host, stats in top_hosts])}
            </tbody>
        </table>
        
        <div class="footer">
            <p>📊 Relatório gerado pelo Fathom Analytics System</p>
            <p>🔗 Sistema desenvolvido para análise de dados do Fathom</p>
        </div>
    </div>
    
    <script>
        // Gráfico mensal
        new Chart(document.getElementById('monthlyChart'), {{
            type: 'line',
            data: {{
                labels: {months},
                datasets: [{{
                    label: 'Chamadas por Mês',
                    data: {monthly_calls},
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Atividade Mensal'
                    }}
                }}
            }}
        }});
        
        // Gráfico de hosts
        new Chart(document.getElementById('hostsChart'), {{
            type: 'bar',
            data: {{
                labels: {host_names},
                datasets: [{{
                    label: 'Número de Chamadas',
                    data: {host_calls},
                    backgroundColor: 'rgba(155, 89, 182, 0.8)',
                    borderColor: '#9b59b6',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Top 10 Hosts por Número de Chamadas'
                    }}
                }}
            }}
        }});
        
        // Gráfico de tópicos
        new Chart(document.getElementById('topicsChart'), {{
            type: 'horizontalBar',
            data: {{
                labels: {topic_names},
                datasets: [{{
                    label: 'Frequência',
                    data: {topic_freq},
                    backgroundColor: 'rgba(46, 204, 113, 0.8)',
                    borderColor: '#2ecc71',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Top 10 Tópicos Mais Discutidos'
                    }}
                }}
            }}
        }});
        
        // Gráfico de duração
        new Chart(document.getElementById('durationChart'), {{
            type: 'doughnut',
            data: {{
                labels: {duration_labels},
                datasets: [{{
                    data: {duration_values},
                    backgroundColor: ['#2ecc71', '#f39c12', '#e74c3c'],
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Distribuição por Duração das Chamadas'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
        """
        
        return html


def main():
    """Função principal do script"""
    
    parser = argparse.ArgumentParser(description='Gerador de relatórios Fathom Analytics')
    parser.add_argument('--format', choices=['console', 'html', 'json'], 
                       default='console', help='Formato do relatório')
    
    args = parser.parse_args()
    
    print("📊 Fathom Analytics - Gerador de Relatórios")
    print("=" * 50)
    
    # Verifica configurações
    if not Config.validate():
        print("❌ Configurações inválidas. Configure o arquivo .env")
        return False
    
    # Inicializa gerador
    generator = FathomReportsGenerator()
    
    # Gera relatório console
    success = generator.generate_console_report()
    
    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        sys.exit(1) 