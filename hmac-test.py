import hmac
import hashlib

digest_maker = hmac.new('secret-shared-key-goes-here', '', hashlib.sha1)

f = open('hmac-test.py', 'rb')
try:
    while True:
        block = f.read(1024)
        if not block:
            break
        digest_maker.update(block)
finally:
    f.close()

digest = digest_maker.hexdigest()
print digest