# Matches the pinned upstream server's Java17/Maven builder; no frontend or telemetry agent.
FROM maven@sha256:a0603aab698040d9c94259f379ec0487da1678560748d6c7508483034033c53d AS build
WORKDIR /source/server
COPY server/pom.xml ./pom.xml
COPY server/src ./src
COPY library /source/library
RUN MAVEN_OPTS="-Xmx1024m" mvn -B -ntp clean package -DskipTests spring-boot:repackage -Pboot

FROM maven@sha256:a0603aab698040d9c94259f379ec0487da1678560748d6c7508483034033c53d
COPY --from=build /source/server/target/ROOT.war /app/reference-payer.war
COPY LICENSE /app/UPSTREAM-LICENSE
LABEL org.opencontainers.image.source="https://github.com/HL7-DaVinci/br-payer"
LABEL org.opencontainers.image.revision="10d40911cb90d6198aacec144b4bfc48466af2fb"
USER 65532:65532
WORKDIR /tmp
EXPOSE 8081
ENTRYPOINT ["java", "-Xmx1536m", "-Dserver.address=0.0.0.0", "-Dserver.port=8081", "-jar", "/app/reference-payer.war"]
