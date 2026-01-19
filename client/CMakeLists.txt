find_package(Python3 REQUIRED)

set(PYTHON_SCRIPT "client_gui.py")

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/${PYTHON_SCRIPT}
               ${CMAKE_CURRENT_BINARY_DIR}/${PYTHON_SCRIPT}
               COPYONLY)

add_custom_target(client ALL
    DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/${PYTHON_SCRIPT}
    COMMAND chmod +x ${CMAKE_CURRENT_BINARY_DIR}/${PYTHON_SCRIPT}
    COMMENT "Przygotowywanie klienta Python (kopiowanie i chmod +x)"
)

find_program(FLAKE8_EXEC flake8)

if(FLAKE8_EXEC)
    add_custom_target(lint_client
        COMMAND ${FLAKE8_EXEC} --ignore=E501 ${CMAKE_CURRENT_SOURCE_DIR}/${PYTHON_SCRIPT}
        COMMENT "Sprawdzanie kodu Pythona (Linting)"
    )
    add_dependencies(client lint_client)
else()
    message(WARNING "Nie znaleziono flake8. Analiza statyczna Pythona pominięta.")
endif()
