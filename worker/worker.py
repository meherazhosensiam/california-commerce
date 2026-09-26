import os,time
import redis
r=redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'))
while True:
 try:
  r.set('cc:worker:heartbeat',str(int(time.time())),ex=30)
 except Exception: pass
 time.sleep(5)
