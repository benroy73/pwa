How to test the jekyll locally on a Mac.

https://docs.github.com/en/pages/setting-up-a-github-pages-site-with-jekyll/adding-a-theme-to-your-github-pages-site-using-jekyll

Setup ruby 3.1
```
brew install ruby@3.1
echo 'export PATH="/opt/homebrew/opt/ruby@3.1/bin:$PATH"' >> ~/.zshrc
echo 'export LDFLAGS="-L/opt/homebrew/opt/ruby@3.1/lib"' >> ~/.zshrc
echo 'export CPPFLAGS="-I/opt/homebrew/opt/ruby@3.1/include"' >> ~/.zshrc

source ~/.zshrc

gem install bundler
bundle install
```

Run the jekyll server to simulate Github pages locally.

```
bundle exec jekyll serve
open http://127.0.0.1:4000
```

Try different themes in the _config.yml file

```
remote_theme: pages-themes/slate@v0.2.0
remote_theme: pages-themes/leap-day@v0.2.0
remote_theme: pages-themes/minimal@v0.2.0
remote_theme: "jekyll/minima@1e8a445"
```
