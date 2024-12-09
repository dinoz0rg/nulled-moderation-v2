$(document).ready(function () {
    // Store the original value on focus
    $(".editable-table td[contenteditable='true']").on("focus", function () {
        $(this).data("original-value", $(this).text().trim());

        if ($(this).hasClass("placeholder")) {
            $(this).removeClass("placeholder");
            $(this).text(""); // Clear placeholder text
        }
    });

    // Compare and save only if value has changed
    $(".editable-table td[contenteditable='true']").on("blur", function () {
        const id = $(this).data("id");
        const tableName = $(this).data("table");
        const newValue = $(this).text().trim();
        const originalValue = $(this).data("original-value");

        if (!newValue && id === "new") {
            $(this).addClass("placeholder");
            $(this).text(`Add new ${tableName}`); // Restore placeholder text
        } else if (id && tableName && newValue !== originalValue) {
            saveChange(id, newValue, tableName);
        }
    });

    function saveChange(id, value, tableName) {
        $.ajax({
            url: `/edit/${tableName}/${id}`,
            type: "POST",
            data: {
                value: value,
            },
            success: function (response) {
                console.log("Change saved successfully.");
                if (id === "new") {
                    location.reload(); // Reload to get the new row with ID
                }
            },
            error: function (xhr, status, error) {
                console.error("Failed to save change:", error);
                alert("Failed to save change. Please try again.");
            },
        });
    }
});
