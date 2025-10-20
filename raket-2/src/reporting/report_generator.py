import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Any
from ..models.token import Token
from ..utils.logger import get_logger

logger = get_logger(__name__)

class ReportGenerator:
    def __init__(self, reports_dir: str):
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)
        logger.info(f"[REPORT] Инициализация генератора отчетов (директория: {reports_dir})")

    def generate_reports(self, rockets: List[Token], report_format: str = "all") -> None:
        """
        Генерирует отчеты о найденных ракетах в указанном формате.
        
        Args:
            rockets: Список токенов-ракет
            report_format: Формат отчета ("json", "csv", "html" или "all")
        """
        logger.info(f"[REPORT] Формирование отчета о {len(rockets)} ракетах (формат: {report_format})")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"rockets_report_{timestamp}"
        
        if report_format in ["json", "all"]:
            self._generate_json_report(rockets, base_filename)
            
        if report_format in ["csv", "all"]:
            self._generate_csv_report(rockets, base_filename)
            
        if report_format in ["html", "all"]:
            self._generate_html_report(rockets, base_filename)

    def _generate_json_report(self, rockets: List[Token], base_filename: str) -> None:
        """Генерирует JSON отчет."""
        report_data = []
        for rocket in rockets:
            rocket_data = {
                "address": rocket.address,
                "name": rocket.name,
                "symbol": rocket.symbol,
                "age_hours": rocket.age_hours,
                "created_at": rocket.created_at.isoformat(),
                "chain_id": rocket.chain_id,
                "risk_level": rocket.risk_level,
                "risks": rocket.risks,
                "warnings": rocket.warnings,
                "contract_info": rocket.contract_info,
                "pairs": []
            }
            
            for pair in rocket.pairs:
                pair_data = {
                    "address": pair.pair_address,
                    "dex": pair.dex_id,
                    "chain_id": pair.chain_id,
                    "price_usd": pair.price_usd,
                    "price_change_1h": pair.price_change_1h,
                    "price_change_24h": pair.price_change_24h,
                    "liquidity_usd": pair.liquidity_usd,
                    "volume_24h": pair.volume_24h,
                    "created_at": pair.created_at.isoformat(),
                    "dex_link": pair.dex_link
                }
                rocket_data["pairs"].append(pair_data)
            
            report_data.append(rocket_data)
        
        report_path = os.path.join(self.reports_dir, f"{base_filename}.json")
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
        logger.info(f"[REPORT] JSON отчет успешно создан: {report_path}")

    def _generate_csv_report(self, rockets: List[Token], base_filename: str) -> None:
        """Генерирует CSV отчет."""
        report_path = os.path.join(self.reports_dir, f"{base_filename}.csv")
        
        with open(report_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Address", "Name", "Symbol", "Age (hours)", "Created At",
                "Chain", "Risk Level", "Price USD", "Price Change 1h (%)",
                "Price Change 24h (%)", "Liquidity USD", "Volume 24h USD",
                "DEX", "DEX Link"
            ])
            
            for rocket in rockets:
                for pair in rocket.pairs:
                    writer.writerow([
                        rocket.address,
                        rocket.name,
                        rocket.symbol,
                        f"{rocket.age_hours:.2f}",
                        rocket.created_at.isoformat(),
                        rocket.chain_id,
                        rocket.risk_level,
                        f"{pair.price_usd:.8f}",
                        f"{pair.price_change_1h:.2f}",
                        f"{pair.price_change_24h:.2f}",
                        f"{pair.liquidity_usd:.2f}",
                        f"{pair.volume_24h:.2f}",
                        pair.dex_id,
                        pair.dex_link
                    ])
        
        logger.info(f"[REPORT] CSV отчет успешно создан: {report_path}")

    def _generate_html_report(self, rockets: List[Token], base_filename: str) -> None:
        """Генерирует HTML отчет."""
        report_path = os.path.join(self.reports_dir, f"{base_filename}.html")
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Rocket Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .risk-high { color: red; }
                .risk-medium { color: orange; }
                .risk-low { color: green; }
            </style>
        </head>
        <body>
            <h1>Rocket Report</h1>
            <p>Generated at: {timestamp}</p>
            <table>
                <tr>
                    <th>Name</th>
                    <th>Symbol</th>
                    <th>Age</th>
                    <th>Chain</th>
                    <th>Risk Level</th>
                    <th>Price USD</th>
                    <th>Price Change 1h</th>
                    <th>Price Change 24h</th>
                    <th>Liquidity USD</th>
                    <th>Volume 24h USD</th>
                    <th>DEX</th>
                    <th>Link</th>
                </tr>
        """.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        for rocket in rockets:
            for pair in rocket.pairs:
                risk_class = f"risk-{rocket.risk_level.lower()}"
                html += f"""
                <tr>
                    <td>{rocket.name}</td>
                    <td>{rocket.symbol}</td>
                    <td>{rocket.age_hours:.2f}h</td>
                    <td>{rocket.chain_id}</td>
                    <td class="{risk_class}">{rocket.risk_level}</td>
                    <td>${pair.price_usd:.8f}</td>
                    <td>{pair.price_change_1h:.2f}%</td>
                    <td>{pair.price_change_24h:.2f}%</td>
                    <td>${pair.liquidity_usd:,.2f}</td>
                    <td>${pair.volume_24h:,.2f}</td>
                    <td>{pair.dex_id}</td>
                    <td><a href="{pair.dex_link}" target="_blank">Trade</a></td>
                </tr>
                """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        with open(report_path, "w") as f:
            f.write(html)
        logger.info(f"[REPORT] HTML отчет успешно создан: {report_path}") 