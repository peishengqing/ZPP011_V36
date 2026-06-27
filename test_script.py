import sys
f = open('test_log.txt', 'w')
f.write('script started\n')
f.write('python version: %s\n' % (sys.version.split()[0]))
f.write('done\n')
f.close()
print('script finished')
