package com.example.floating.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {
    @Bean
    WebClient webClient() {
        return WebClient.builder().exchangeStrategies(ExchangeStrategies.builder()
                        .codecs(configurer
                                -> configurer.defaultCodecs().maxInMemorySize(-1)) //무제한 버퍼
                        .build())
                .baseUrl("http://localhost:8000")   // 업로드한 파일을 ai 서버에 전송하기 위해서 버퍼의 크기 제한을 제한 없이
                .build();  //https://m.blog.naver.com/seek316/223337685249
    }
}
