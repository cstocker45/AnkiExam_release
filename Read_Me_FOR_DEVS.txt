I set up the fly.io server, which is accessible at https://colestocker.fly.dev
This is serving as the server side webhosting which we will integrate with some type of sql
database to store usernames, passwords, and tokens used...

This is key for tallying up all the costs and later on also setting up payment system
Probably will use stripe...

This is all under library/users/colestocker/AnkiExamServer

This was all a very simple setup...
Putting docker file and stuff in the folder and then running:
export FLYCTL_INSTALL="/Users/colestocker/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"

source ~/.zshrc


flyctl auth login
flyctl launch
flyctl deploy

to reboot the server just run 
flyctl scale count 0
flyctl deploy

PASSWORD FOR THE AnkiExam0 email
ankiexam0@gmail.com
0w56LJxwOufHwv62fsc7


LOGIN DETAILS FOR BACKDOOR
admin:0w56LJxwOufHwv62fsc7

#list all registered users
curl -X GET https://colestocker.fly.dev/admin/users -u admin:0w56LJxwOufHwv62fsc7

#check pending users
curl -X GET https://colestocker.fly.dev/admin/pending -u admin:0w56LJxwOufHwv62fsc7

#delete user
curl -X DELETE https://colestocker.fly.dev/admin/users/{username} -u admin:0w56LJxwOufHwv62fsc7

#delete pending user
curl -X DELETE https://colestocker.fly.dev/admin/pending/{username} -u admin:0w56LJxwOufHwv62fsc7


ANKI EXAM ADDON GOOGLE PASSWORD
eegy ggqa tlbp shvn
