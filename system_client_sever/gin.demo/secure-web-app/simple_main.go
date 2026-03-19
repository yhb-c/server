package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

func securityHeaders(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		expectedHost := "localhost:8083"
		
		if r.Host != expectedHost {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": "Invalid host header"})
			return
		}
		
		w.Header().Set("X-Frame-Options", "DENY")
		cspPolicy := "default-src 'self'; connect-src *; font-src *; " +
			"script-src-elem * 'unsafe-inline'; img-src * data:; style-src * 'unsafe-inline';"
		w.Header().Set("Content-Security-Policy", cspPolicy)
		w.Header().Set("X-XSS-Protection", "1; mode=block")
		w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
		w.Header().Set("Referrer-Policy", "strict-origin")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		permPolicy := "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=()," +
			"magnetometer=(),gyroscope=(),fullscreen=(self),payment=()"
		w.Header().Set("Permissions-Policy", permPolicy)
		
		next(w, r)
	}
}

func serveStatic(w http.ResponseWriter, r *http.Request) {
	log.Printf("请求路径: %s", r.URL.Path)
	
	path := r.URL.Path
	if path == "/" {
		path = "/index.html"
	}
	
	filePath := filepath.Join("public", path)
	log.Printf("文件路径: %s", filePath)
	
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		log.Printf("文件不存在: %s", filePath)
		http.NotFound(w, r)
		return
	}
	
	log.Printf("提供文件: %s", filePath)
	http.ServeFile(w, r, filePath)
}

func apiHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	response := map[string]string{
		"message": "Uniform API",
		"status":  "success",
		"time":    time.Now().Format("2006-01-02 15:04:05"),
	}
	json.NewEncoder(w).Encode(response)
}

func main() {
	httpPort := os.Getenv("API_PORT")
	if httpPort == "" {
		httpPort = "8083"
	}
	
	// 设置路由
	http.HandleFunc("/", securityHeaders(serveStatic))
	http.HandleFunc("/api", securityHeaders(apiHandler))
	http.HandleFunc("/api/", securityHeaders(apiHandler))
	
	// 创建服务器
	srv := &http.Server{
		Addr:              ":" + httpPort,
		ReadHeaderTimeout: 5 * time.Second,
	}
	
	fmt.Printf("🔐 安全Web应用启动成功！\n")
	fmt.Printf("📍 访问地址: http://localhost:%s\n", httpPort)
	fmt.Printf("🛡️  包含完整的安全头设置\n")
	fmt.Printf("📱 支持登录界面和API测试\n\n")
	
	if err := srv.ListenAndServe(); err != nil {
		log.Printf("服务器启动失败: %v", err)
	}
}