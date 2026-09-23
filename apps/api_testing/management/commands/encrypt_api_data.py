"""加密接口测试入参（body/params/headers）存量明文数据"""
from django.core.management.base import BaseCommand

from apps.api_testing.models import ApiRequest


class Command(BaseCommand):
    help = '将 ApiRequest 的 body/params/headers 存量明文加密落库'

    def handle(self, *args, **options):
        count = 0
        for req in ApiRequest.objects.all().iterator():
            req.save(update_fields=['body', 'params', 'headers'])
            count += 1
        self.stdout.write(self.style.SUCCESS(f'已加密 {count} 条接口入参'))
