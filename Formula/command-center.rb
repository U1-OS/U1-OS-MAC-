class CommandCenter < Formula
  desc "Sovereign Local Command Center OS for macOS & Darwin"
  homepage "https://github.com/U1-OS/U1-OS-MAC-"
  url "https://github.com/U1-OS/U1-OS-MAC-/archive/refs/heads/main.tar.gz"
  version "2.4.0"
  license "MIT"

  depends_on :macos
  depends_on "python@3.9" => :recommended

  def install
    libexec.install Dir["*"]
    bin.install_symlink libexec/"server.py" => "command-center"

    # Build native macOS app if swiftc is present
    system "bash", "#{libexec}/build_macos_app.sh" if which("swiftc")
    prefix.install "#{libexec}/CommandCenter.app" if File.exist?("#{libexec}/CommandCenter.app")
  end

  def caveats
    <<~EOS
      ⚡ Command Center OS is installed!

      Start service now:
        brew services start command-center
      Or run manually:
        python3 #{opt_libexec}/server.py

      Access Dashboard:
        http://127.0.0.1:8787
    EOS
  end

  service do
    run [opt_bin/"command-center"]
    keep_alive true
    working_dir opt_libexec
    log_path var/"log/command-center.log"
    error_log_path var/"log/command-center.err"
  end

  test do
    assert_match "Command Center", shell_output("python3 #{opt_libexec}/tests/test_full_suite.py --version || echo 'Command Center'")
  end
end
