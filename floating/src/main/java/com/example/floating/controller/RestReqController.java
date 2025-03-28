package com.example.floating.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;

@RestController
public class RestReqController {

    @Autowired
    private WebClient webClient;

    @PostMapping("/java_service")
    public String serviceRequest(@RequestParam("file") MultipartFile file,
                                 @RequestParam(value = "message", required = false) String message) {
        MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();

        if (file != null && !file.isEmpty()) {
            bodyBuilder.part("file", file.getResource())
                    .filename(file.getOriginalFilename());
        } else {
            throw new IllegalArgumentException("파일이 전달되지 않았습니다.");
        }

        if (message != null) {
            bodyBuilder.part("message", message);
        }

        String result = webClient.post()
                .uri("http://localhost:8000/detect") // FastAPI 서버 주소
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(bodyBuilder.build()))
                .retrieve()
                .bodyToMono(String.class)
                .block();

        return result;
    }

}