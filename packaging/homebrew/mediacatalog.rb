class Mediacatalog < Formula
  include Language::Python::Virtualenv

  desc "Generate printable A5 pages and EPUBs for a media catalog from IMDb IDs"
  homepage "https://github.com/YOUR_GITHUB_USER/media-catalog"
  url "https://github.com/YOUR_GITHUB_USER/media-catalog/archive/refs/tags/v0.1.1.tar.gz"
  sha256 "REPLACE_WITH_TARBALL_SHA256"
  license "GPL-3.0-or-later"

  depends_on "python@3.12"

  resource "ebooklib" do
    url "https://files.pythonhosted.org/packages/source/e/ebooklib/ebooklib-0.20.tar.gz"
    sha256 "1a0e9a52b50740a4ca3b3683ed6e537c2ff2c9fe178e20224da294d47c0a103b"
  end

  resource "pypdf" do
    url "https://files.pythonhosted.org/packages/source/p/pypdf/pypdf-6.5.0.tar.gz"
    sha256 "b4b8f2cbb864d81130344f89ad613025304d1b9f39d3e64dc6b740c8dc2c517b"
  end

  resource "python-dotenv" do
    url "https://files.pythonhosted.org/packages/source/p/python-dotenv/python-dotenv-1.2.1.tar.gz"
    sha256 "a665d7b75f34b5ec2cfa32b3cd9b2b6ee9d8a90a61c5a3b46fc0b086347f7e63"
  end

  resource "reportlab" do
    url "https://files.pythonhosted.org/packages/source/r/reportlab/reportlab-4.4.7.tar.gz"
    sha256 "c28deaa1a2f311cdfbf9b59ddc8f1b1c61c6e5b118870c1bd7e7807196e21a64"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.32.5.tar.gz"
    sha256 "dbba0bac56e100853db0ea71b82b4dfd5fe2bf6d3754a8893c3af500cec7d7cf"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/mediacatalog", "--help"
  end
end
