#include <gtest/gtest.h>
#include <string>

// Simple test that doesn't depend on external files
TEST(BasicTest, StringOperations) {
    std::string hello = "Hello";
    std::string world = "World";
    std::string result = hello + " " + world;
    
    EXPECT_EQ(result, "Hello World");
    EXPECT_NE(hello, world);
    EXPECT_TRUE(result.find("Hello") != std::string::npos);
}

TEST(BasicTest, MathOperations) {
    EXPECT_EQ(2 + 2, 4);
    EXPECT_GT(5, 3);
    EXPECT_LT(1, 10);
    EXPECT_DOUBLE_EQ(3.14159, 3.14159);
}

TEST(BasicTest, BooleanLogic) {
    EXPECT_TRUE(true);
    EXPECT_FALSE(false);
    EXPECT_TRUE(1 == 1);
    EXPECT_FALSE(1 == 0);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
