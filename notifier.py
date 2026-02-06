"""
再入荷通知モジュール
Discord Webhookへの通知送信機能を提供
"""
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime


class DiscordNotifier:
    """Discord Webhook通知クラス"""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        初期化

        Args:
            webhook_url: Discord Webhook URL（未指定の場合は環境変数から取得）
        """
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

    def send_restock_notification(self, restock_items: List[Dict]) -> bool:
        """
        再入荷情報をDiscordに通知

        Args:
            restock_items: 再入荷アイテムのリスト

        Returns:
            通知成功: True、失敗: False
        """
        if not self.enabled or not restock_items:
            return False

        # Embedsを構築（最大10件まで）
        embeds = []
        for item in restock_items[:10]:
            embed = {
                "title": item['product_title'][:256],  # 最大256文字
                "url": item['product_url'],
                "color": 0xFF9800,  # オレンジ色（再入荷）
                "fields": [
                    {
                        "name": "📅 再入荷日",
                        "value": item.get('new_event_date', '不明'),
                        "inline": True
                    }
                ],
                "timestamp": item.get('detected_at', datetime.now().isoformat())
            }

            # 以前の発売日がある場合
            if item.get('previous_event_date'):
                embed["fields"].append({
                    "name": "📆 以前の発売日",
                    "value": item['previous_event_date'],
                    "inline": True
                })

            embeds.append(embed)

        # メッセージペイロード構築
        payload = {
            "content": f"🔔 **ちいかわマーケット再入荷情報** ({len(restock_items)}件)",
            "embeds": embeds
        }

        # Discord Webhookに送信
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"  ⚠️ Discord通知エラー: {e}")
            return False

    def send_summary(self, total_collected: int, total_restocks: int) -> bool:
        """
        収集サマリーをDiscordに通知

        Args:
            total_collected: 新規収集件数
            total_restocks: 再入荷検出件数

        Returns:
            通知成功: True、失敗: False
        """
        if not self.enabled:
            return False

        embed = {
            "title": "✅ ちいかわ情報収集完了",
            "color": 0x4CAF50,  # 緑色
            "fields": [
                {
                    "name": "📦 新規収集",
                    "value": f"{total_collected}件",
                    "inline": True
                },
                {
                    "name": "🔔 再入荷検出",
                    "value": f"{total_restocks}件",
                    "inline": True
                }
            ],
            "timestamp": datetime.now().isoformat()
        }

        payload = {"embeds": [embed]}

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"  ⚠️ Discord通知エラー: {e}")
            return False
